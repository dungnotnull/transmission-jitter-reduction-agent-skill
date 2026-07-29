"""tools/test_agent_framework.py -- tests for the agent framework modules.

Covers tjr.config, tjr.logging_utils, tjr.context, tjr.tools, tjr.hooks,
tjr.skills and tjr.agents. Pure, deterministic, no network, no LLM.

Run: ``python tools/test_agent_framework.py``  (or ``pytest tools/test_agent_framework.py``)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402  (optional; standalone runner works without it)


# --------------------------------------------------------------------------- #
# tjr.config
# --------------------------------------------------------------------------- #
def test_config_defaults_load():
    from tjr.config import load_settings
    s = load_settings()
    assert s.environment == "production"
    assert s.llm.temperature == 0.2
    assert s.features.agent_framework is True
    assert s.logging.format == "json"


def test_config_env_override(monkeypatch=None):
    from tjr.config import load_settings
    env = {"TJR_ENVIRONMENT": "development", "TJR_LLM_TEMPERATURE": "0.7",
           "TJR_LOGGING_LEVEL": "DEBUG"}
    old = {k: os.environ.get(k) for k in env}
    try:
        os.environ.update(env)
        s = load_settings()
        assert s.environment == "development"
        assert s.llm.temperature == 0.7
        assert s.logging.level == "DEBUG"
    finally:
        for k in env:
            if old[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old[k]


def test_config_explicit_override():
    from tjr.config import load_settings
    s = load_settings(overrides={"llm": {"temperature": 0.05, "model": "claude-opus-4"}})
    assert s.llm.temperature == 0.05
    assert s.llm.model == "claude-opus-4"


def test_config_invalid_raises():
    from tjr.config import load_settings, ConfigError
    with pytest.raises(ConfigError):
        load_settings(overrides={"llm": {"temperature": 99.0}})  # > maximum 2.0
    with pytest.raises(ConfigError):
        load_settings(overrides={"logging": {"level": "BOGUS"}})  # not in choices


def test_config_as_dict_roundtrip():
    from tjr.config import load_settings
    s = load_settings()
    d = s.as_dict()
    assert d["features"]["agent_framework"] is True
    json.loads(s.to_json())


def test_config_toml_subset_parser(tmp_path):
    from tjr.config import load_toml
    p = tmp_path / "t.toml"
    p.write_text('[features]\nagent_framework = false\nkey = "x"\nnum = 3\n', encoding="utf-8")
    d = load_toml(p)
    assert d["features"]["agent_framework"] is False
    assert d["features"]["key"] == "x"
    assert d["features"]["num"] == 3


# --------------------------------------------------------------------------- #
# tjr.logging_utils
# --------------------------------------------------------------------------- #
def test_logging_json_format(capsys=None):
    from tjr.logging_utils import configure_logging, log_event, get_logger
    lg = configure_logging(fmt="json", output="stderr", level="INFO")
    log_event(lg, "test.event", step=1, flag=True)
    # No exception means success; structured fields attached.


def test_logging_text_format():
    from tjr.logging_utils import configure_logging, log_event
    lg = configure_logging(fmt="text", output="stdout", level="INFO")
    log_event(lg, "test.text", n=2)
    configure_logging(fmt="json", output="stderr", level="INFO")  # restore


def test_logging_file_fallback(tmp_path):
    from tjr.logging_utils import configure_logging
    # An unwritable path must fall back to stderr without crashing.
    lg = configure_logging(output="/no/such/dir/that/exists/log.json", level="INFO")
    assert lg.name == "tjr"
    configure_logging(fmt="json", output="stderr", level="INFO")


# --------------------------------------------------------------------------- #
# tjr.context
# --------------------------------------------------------------------------- #
def test_token_estimator_positive():
    from tjr.context import TokenEstimator
    e = TokenEstimator()
    assert e.count("") == 0
    assert e.count("hello world") >= 1
    assert e.count({"a": [1, 2, 3]}) >= 1


def test_token_budget_spend_reserve():
    from tjr.context import TokenBudget
    b = TokenBudget(total=100, label="t")
    assert b.remaining == 100
    assert b.spend(30) == 30 and b.spent == 30
    assert b.reserve(50) == 50
    assert b.spend(40) == 40 and b.reserved == 10 and b.spent == 70
    b.release(5)
    assert b.reserved == 5
    assert b.exhausted is False
    b.spend(100)  # over-spend clamps
    assert b.exhausted is True


def test_token_budget_invalid():
    from tjr.context import TokenBudget
    with pytest.raises(ValueError):
        TokenBudget(total=0)


def test_context_window_truncation():
    from tjr.context import ContextWindow, TokenEstimator
    w = ContextWindow(estimator=TokenEstimator(), max_tokens=30)
    w.add_system("system prompt")              # pinned
    w.add("user", "x" * 500)                    # evicted
    assert w.tokens <= w.max_tokens
    assert any(e.role == "system" for e in w.entries)
    assert all(e.role != "user" for e in w.entries)


def test_context_window_to_messages():
    from tjr.context import ContextWindow
    w = ContextWindow(max_tokens=1000)
    w.add_system("sys")
    w.add("user", "hi")
    w.add_grounding("ground")  # grounding excluded from messages
    msgs = w.to_messages()
    assert [m["role"] for m in msgs] == ["system", "user"]


# --------------------------------------------------------------------------- #
# tjr.tools
# --------------------------------------------------------------------------- #
def test_tools_registry_execute_ok():
    from tjr.tools import default_registry
    r = default_registry()
    res = r.execute("compute_jitter", {"rtts": [10, 12, 11, 13, 9]})
    assert res.ok and res.value["n"] == 5
    assert "duration_ms" in res.as_dict()


def test_tools_registry_schema_fail():
    from tjr.tools import default_registry
    r = default_registry()
    res = r.execute("compute_jitter", {"rtts": []})  # minItems 1
    assert not res.ok and "fewer than" in res.error
    res2 = r.execute("nonexistent", {})
    assert not res2.ok and "unknown tool" in res2.error


def test_tools_registry_handler_error_captured():
    from tjr.tools import default_registry
    r = default_registry()
    res = r.execute("bufferbloat_grade",
                    {"latency_under_load_ms": float("inf"), "idle_latency_ms": 10})
    assert not res.ok and "ValueError" in res.error


def test_tools_registry_duplicate_register():
    from tjr.tools import ToolRegistry, ToolError, default_registry, register_default_tools
    r = ToolRegistry()
    register_default_tools(r)
    with pytest.raises(ToolError):
        register_default_tools(r)  # duplicate names


def test_tools_verdict_enum_output():
    from tjr.tools import default_registry
    r = default_registry()
    res = r.execute("verdict_from_scorecard",
                    {"jitter_ms": 3, "bufferbloat_grade_letter": "A"})
    assert res.ok and res.value == "Low Jitter"


# --------------------------------------------------------------------------- #
# tjr.hooks
# --------------------------------------------------------------------------- #
def test_hooks_event_bus_isolation():
    from tjr.hooks import EventBus, HookType, Event
    bus = EventBus()
    calls = []
    def good(ev, st): calls.append(ev.type)
    def bad(ev, st): raise RuntimeError("boom")
    bus.subscribe(HookType.POST_STEP, good)
    bus.subscribe(HookType.POST_STEP, bad)
    st = {}
    bus.emit(Event(HookType.POST_STEP, {"output": 1}, "x"), st)
    bus.emit(Event(HookType.POST_STEP, {"output": 2}, "y"), st)
    # good called twice; bad disabled after first error
    assert calls == [HookType.POST_STEP, HookType.POST_STEP]
    assert len(bus.history()) == 2


def test_hooks_metrics_and_state_snapshot():
    from tjr.hooks import default_hooks, HookType
    hm = default_hooks()
    st = {}
    hm.emit(HookType.POST_STEP, "gather_requirements", {"output": {"obj": "net"}}, st)
    hm.emit(HookType.ON_DEGRADATION, "router", {"level": 2}, st)
    hm.emit(HookType.ON_GATE, "U1", {"passed": False}, st)
    assert st["metrics"]["steps_run"] == 1
    assert st["metrics"]["degradations"] == 1
    assert st["metrics"]["gates_failed"] == 1
    assert st.get("requirements") == {"obj": "net"}


def test_hooks_token_accounting():
    from tjr.hooks import default_hooks, HookType
    from tjr.context import TokenBudget, TokenEstimator
    hm = default_hooks(estimator=TokenEstimator())
    b = TokenBudget(total=10000, label="t")
    st = {"token_budget": b}
    hm.emit(HookType.POST_STEP, "core", {"output": "x" * 1000}, st)
    assert b.spent > 0
    assert st["token_spent"] == b.spent


# --------------------------------------------------------------------------- #
# tjr.skills
# --------------------------------------------------------------------------- #
def test_skills_registry_execute_ok():
    from tjr.skills import default_registry
    r = default_registry()
    res = r.execute("gather_requirements", {"query": "analyze jitter", "game": "valorant"})
    assert res.ok and res.output["analysis_type"] == "combined"
    assert res.output["language"] == "en"


def test_skills_registry_schema_validation():
    from tjr.skills import default_registry
    r = default_registry()
    # inputs_schema has no required props, but outputs requires coverage enum.
    res = r.execute("knowledge_updater", {"knowledge_citations": [{"title": "x"}]})
    assert res.ok and res.output["coverage"] in {"Strong", "Moderate", "Weak"}


def test_skills_router_full_plan():
    from tjr.skills import default_registry, ChainOfThoughtRouter
    r = default_registry()
    rt = ChainOfThoughtRouter(r)
    ctx = {"query": "analyze jitter", "rtt_samples": [10, 12], "idle_latency_ms": 10,
           "latency_under_load_ms": 30, "evidence": [{"source": "x"}],
           "knowledge_citations": [{"title": "y"}]}
    p = rt.plan(ctx)
    assert p.plan == ["gather_requirements", "evidence_collector", "core_analysis",
                      "knowledge_updater", "advisor"]
    assert p.degraded is False
    assert p.trace  # non-empty chain-of-thought


def test_skills_router_degraded_no_data():
    from tjr.skills import default_registry, ChainOfThoughtRouter
    rt = ChainOfThoughtRouter(default_registry())
    p = rt.plan({"query": "analyze"})
    assert p.degraded is True
    assert p.short_circuit == "Inconclusive"


def test_skills_router_informational():
    from tjr.skills import default_registry, ChainOfThoughtRouter
    rt = ChainOfThoughtRouter(default_registry())
    p = rt.plan({"query": "explain AQM"})
    assert "evidence_collector" not in p.plan
    assert p.short_circuit == "Inconclusive"


def test_skills_resolve_fuzzy():
    from tjr.skills import default_registry
    r = default_registry()
    names = r.resolve("jitter buffer wi-fi aqm")
    assert "core_analysis" in names


def test_skills_duplicate_register():
    from tjr.skills import SkillRegistry, SkillSpec, SkillError, default_registry, register_default_skills
    r = SkillRegistry()
    register_default_skills(r)
    with pytest.raises(SkillError):
        register_default_skills(r)


def test_skills_advisor_via_state_snapshot():
    from tjr.skills import default_registry
    r = default_registry()
    st = {"core_analysis": {"degraded": False, "jitter_ms": 3, "bufferbloat_grade": "A"}}
    res = r.execute("advisor", {"isp_limited": False}, state=st)
    assert res.ok and res.output["verdict"] == "Low Jitter"


# --------------------------------------------------------------------------- #
# tjr.agents
# --------------------------------------------------------------------------- #
def test_agent_run_full():
    from tjr.agents import OrchestratorAgent
    ctx = {"query": "analyze jitter for valorant",
           "rtt_samples": [14.2, 13.9, 15.1, 22.8, 14.1, 13.8, 15.0, 14.2,
                           13.9, 15.1, 14.0, 13.9],
           "idle_latency_ms": 14, "latency_under_load_ms": 78,
           "upload_mbps": 20, "download_mbps": 100, "game": "valorant",
           "evidence": [{"source": "RFC 8290", "tier": 1, "date": "cached",
                         "url": "https://www.rfc-editor.org/rfc/rfc8290"}],
           "knowledge_citations": [{"title": "FQ-CoDel", "tier": 1,
                       "doi_or_url": "https://www.rfc-editor.org/rfc/rfc8290"}]}
    r = OrchestratorAgent().run(ctx)
    assert r.verdict in {"Low Jitter", "Conditional (ISP-limited)", "High Jitter", "Inconclusive"}
    assert r.plan == ["gather_requirements", "evidence_collector", "core_analysis",
                      "knowledge_updater", "advisor"]
    assert len(r.trace) > 0
    assert "steps_run" in r.metrics
    json.loads(r.to_json())


def test_agent_run_degraded_no_data():
    from tjr.agents import OrchestratorAgent
    r = OrchestratorAgent().run({"query": "analyze"})
    assert r.verdict == "Inconclusive"
    assert r.degraded is True


def test_agent_run_quiet_settings():
    from tjr.agents import OrchestratorAgent
    from tjr.config import load_settings
    s = load_settings(overrides={"logging": {"level": "WARNING"}})
    r = OrchestratorAgent(settings=s).run({"query": "analyze", "rtt_samples": [10, 12, 11, 13, 9],
                                           "idle_latency_ms": 10, "latency_under_load_ms": 12})
    assert r.verdict in {"Low Jitter", "Conditional (ISP-limited)", "High Jitter", "Inconclusive"}


def test_agent_result_has_report_markdown():
    from tjr.agents import OrchestratorAgent
    r = OrchestratorAgent().run({"query": "x", "rtt_samples": [1, 2, 3], "idle_latency_ms": 1, "latency_under_load_ms": 2})
    assert "Post-Execution Gate Checklist" in r.report_markdown


# --------------------------------------------------------------------------- #
# Standalone runner (no pytest required)
# --------------------------------------------------------------------------- #
def _run_all() -> int:
    import inspect
    failures = 0
    g = globals()
    for name, fn in list(g.items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
            kwargs = {}
            if "tmp_path" in sig.parameters:
                kwargs["tmp_path"] = Path(tempfile.mkdtemp())
            if "capsys" in sig.parameters or "monkeypatch" in sig.parameters:
                kwargs = {k: None for k in sig.parameters}
            fn(**kwargs)
            print(f"[OK] {name}")
        except Exception as ex:
            print(f"[FAIL] {name}: {ex}")
            failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)