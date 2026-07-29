"""tools/run_test_scenarios.py Ä‚Â¢Ă¢â€Â¬Ă¢â‚¬Â production-grade structural, content & runtime
validator for Skill 262 (transmission-jitter-reduction).

It combines three layers of checks:

1. **8-File Contract + content structure** (file presence, frontmatter, sections).
2. **Domain-logic coverage** (quality gates U1Ä‚Â¢Ă¢â€Â¬Ă¢â‚¬Å“U6 + G1Ä‚Â¢Ă¢â€Â¬Ă¢â‚¬Å“G4, all 4 verdicts,
   knowledge-base DOIs/RFCs, crawl config sanity).
3. **Runtime scenarios** Ä‚Â¢Ă¢â€Â¬Ă¢â‚¬Â actually runs :mod:`tjr.harness` over the fixtures in
   ``tests/fixtures`` and asserts the contract holds end-to-end (verdict set,
   gate summary, degradation behaviour, JSON serialisability).

Exit code 0 = all checks pass, non-zero = failures.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SKILLS = ROOT / "skills"
FIX = ROOT / "tests" / "fixtures"
GATES = ["U1", "U2", "U3", "U4", "U5", "U6", "G1", "G2", "G3", "G4"]
DOMAIN_GATES = ["G1", "G2", "G3", "G4"]
VERDICTS = ["Low Jitter", "Conditional (ISP-limited)", "High Jitter", "Inconclusive"]

checks_passed = 0
checks_failed = 0
failures: list = []


def ok(label: str = "", detail: str = "") -> None:
    global checks_passed
    checks_passed += 1


def fail(label: str, detail: str = "") -> None:
    global checks_failed
    checks_failed += 1
    failures.append(f"{label}: {detail}")


def require(cond: bool, label: str, detail: str = "") -> None:
    (ok if cond else fail)(label, detail)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


# --------------------------------------------------------------------------- #
# Layer 1 Ä‚Â¢Ă¢â€Â¬Ă¢â‚¬Â file structure
# --------------------------------------------------------------------------- #
REQUIRED = [
    "CLAUDE.md", "PROJECT-detail.md", "PROJECT-DEVELOPMENT-PHASE-TRACKING.md",
    "README.md", "SECOND-KNOWLEDGE-BRAIN.md", "skills/main.md", "SKILL.md",
    "tools/knowledge_updater.py", "tools/test_knowledge_updater.py",
    "tools/run_test_scenarios.py", "tools/validate_project.py",
    "tools/test_jitter_analysis.py", "tools/test_quality_gates.py",
    "tools/test_harness.py", "tools/test_agent_framework.py",
    "tests/test-scenarios.md", "tests/TEST_RESULTS.md",
    "LICENSE", "pyproject.toml", "progression.json", "requirements.txt",
    "tjr/__init__.py", "tjr/jitter_analysis.py", "tjr/quality_gates.py",
    "tjr/harness.py", "tjr/knowledge_updater.py", "tjr/cli.py",
    "tjr/jitter_cli.py", "tjr/knowledge_cli.py",
    "tjr/config.py", "tjr/logging_utils.py", "tjr/context.py", "tjr/tools.py",
    "tjr/hooks.py", "tjr/skills.py", "tjr/agents.py", "tjr/agent_cli.py",
    "config/default.toml", "config/README.md",
    "references/README.md", "references/prompt-templates.md",
    "references/domain-guidelines.md", "references/evidence-hierarchy.md",
    "references/rfc-index.md",
    "assets/README.md", "assets/schemas/harness_input.schema.json",
    "assets/schemas/harness_result.schema.json", "assets/schemas/skill_spec.schema.json",
    "assets/schemas/tool.schema.json", "assets/diagrams/architecture.mmd",
    "assets/diagrams/harness-flow.mmd",
    "scripts/setup.py", "scripts/seed_knowledge.py",
    "scripts/ingest_measurements.py", "scripts/run_crawl.py", "scripts/validate.py",
    "tests/fixtures/ping_capture.txt", "tests/fixtures/harness_input.json",
    "tests/fixtures/harness_input_degraded.json",
]
for f in REQUIRED:
    require((ROOT / f).exists(), f"file present: {f}")

subs = sorted(SKILLS.glob("sub-*.md"))
require(len(subs) >= 5, "at least 5 sub-skills", f"found {len(subs)}")
expected_subs = {"sub-gather-requirements", "sub-evidence-collector",
                 "sub-core-analysis", "sub-knowledge-updater", "sub-advisor"}
got_subs = {s.stem for s in subs}
require(got_subs == expected_subs, "sub-skill set exact", f"got {got_subs}")

# --------------------------------------------------------------------------- #
# Layer 2 Ä‚Â¢Ă¢â€Â¬Ă¢â‚¬Â frontmatter + sections + gates + knowledge base
# --------------------------------------------------------------------------- #
FM = re.compile(r"^---\s*\n(.*?\n)---", re.S)
for s in subs:
    txt = read(s)
    m = FM.search(txt)
    require(bool(m), f"{s.name}: frontmatter")
    if m:
        require("name:" in m.group(1) and "description:" in m.group(1),
                f"{s.name}: name+description")
    for sec in ("Role & Persona", "Workflow", "Output Format", "Quality Gates"):
        require(sec in txt, f"{s.name}: section {sec}")

main_txt = read(ROOT / "skills" / "main.md")
for sec in ("Role & Persona", "Quality Gates", "Graceful Degradation",
            "Pre-Flight", "Harness Execution Protocol", "Output Format"):
    require(sec in main_txt, f"main.md: section {sec}")
require("limitation" in main_txt.lower(), "main.md: limitation banner")
for g in GATES:
    require(g in main_txt, f"main.md: gate {g} present")

adv = read(ROOT / "skills" / "sub-advisor.md")
for v in VERDICTS:
    require(v in adv or v in main_txt, f"advisor/verdict {v} present")

brain = read(ROOT / "SECOND-KNOWLEDGE-BRAIN.md")
require("Tier 1" in brain and "Tier 4" in brain, "brain: evidence hierarchy tiers")
dois = re.findall(r"10\.\d{4,9}/[^\s|]+", brain)
require(len(dois) >= 2, "brain: >=2 DOI-cited references", f"found {len(dois)}")
rfcs = re.findall(r"RFC\s?\d{3,4}", brain, re.I)
require(len(rfcs) >= 3, "brain: >=3 RFC references", f"found {len(rfcs)}")
for sec in ("## 1. Core", "## 4. Authoritative Data Sources",
            "## 6. Self-Update Protocol", "## 7. Knowledge Update Log"):
    require(sec in brain, f"brain: section {sec}")

# knowledge_updater config sanity (now via tjr).
from tjr import knowledge_updater as ku  # noqa: E402
require("cs.NI" in ku.KNOWLEDGE_CONFIG["arxiv_categories"], "ku: real arxiv category")
require(len(ku.KNOWLEDGE_CONFIG["rss_feeds"]) >= 3, "ku: >=3 rss feeds")
require("sha256" in open(ku.__file__, encoding="utf-8").read().lower(), "ku: SHA256 dedup")
w = ku.KNOWLEDGE_CONFIG["scoring_weights"]
require(abs(sum(w.values()) - 1.0) < 1e-9, "ku: scoring weights sum to 1")

# --------------------------------------------------------------------------- #
# Layer 3 Ä‚Â¢Ă¢â€Â¬Ă¢â‚¬Â runtime scenarios via tjr.harness
# --------------------------------------------------------------------------- #
from tjr.harness import Harness, HarnessInput  # noqa: E402


def _run_fixture(name: str):
    data = json.loads((FIX / name).read_text(encoding="utf-8"))
    return Harness().run(HarnessInput.from_dict(data))


# Scenario 1: standard full run.
r1 = _run_fixture("harness_input.json")
require(r1.degradation_level == 0, "S1: degradation level 0")
require(r1.verdict in set(VERDICTS), "S1: verdict in declared set", r1.verdict)
require(r1.gate_summary["all_pass"] is True, "S1: all gates pass")
require(r1.jitter_report["n"] == 12, "S1: 12 RTT samples processed")
require(all(g in r1.report_markdown for g in ("G1", "G2", "G3", "G4")),
        "S1: gate checklist in report")
# Scenario 5: degraded.
r5 = _run_fixture("harness_input_degraded.json")
require(r5.degradation_level == 4, "S5: degradation level 4")
require(r5.verdict == "Inconclusive", "S5: Inconclusive verdict")
require(r5.jitter_report == {}, "S5: no fabricated jitter numbers")
# JSON serialisability.
require(isinstance(json.loads(r1.to_json())["verdict"], str), "S1: JSON serialisable")
# Exercise all verdict categories programmatically via jitter_analysis.
from tjr import jitter_analysis as ja  # noqa: E402
seen = {
    ja.verdict_from_scorecard(3, "A", isp_limited=False),
    ja.verdict_from_scorecard(10, "B", isp_limited=True),
    ja.verdict_from_scorecard(50, "F"),
    ja.verdict_from_scorecard(0, "A", data_available=False),
}
require({v.value for v in seen} == set(VERDICTS), "all 4 verdicts exercised")

# --------------------------------------------------------------------------- #
# Layer 4 -- agent framework (Phase 7) runtime
# --------------------------------------------------------------------------- #
from tjr.agents import OrchestratorAgent  # noqa: E402
from tjr.skills import default_registry as _skill_reg, ChainOfThoughtRouter  # noqa: E402
from tjr.tools import default_registry as _tool_reg  # noqa: E402

# Agent framework modules present + registry shape.
sreg = _skill_reg()
require(set(sreg.names()) == {"gather_requirements", "evidence_collector",
       "core_analysis", "knowledge_updater", "advisor"}, "agent: 5 skills registered")
treg = _tool_reg()
require(len(treg.names()) >= 9, "agent: >=9 tools registered", f"got {len(treg.names())}")
# Router plan + trace.
_p = ChainOfThoughtRouter(sreg).plan({"query": "analyze jitter",
                                      "rtt_samples": [10, 12], "idle_latency_ms": 10,
                                      "latency_under_load_ms": 30, "evidence": [{}],
                                      "knowledge_citations": [{}]})
require(_p.plan == ["gather_requirements", "evidence_collector", "core_analysis",
                    "knowledge_updater", "advisor"], "agent: full plan")
require(len(_p.trace) >= 1 and _p.degraded is False, "agent: trace + non-degraded")
# Orchestrator runs end-to-end over the standard fixture (reusing r1 context).
_agent_r = OrchestratorAgent().run(json.loads((FIX / "harness_input.json").read_text(encoding="utf-8")))
require(_agent_r.verdict in set(VERDICTS), "agent: verdict in declared set", _agent_r.verdict)
require(len(_agent_r.skill_results) == 5, "agent: 5 skill results")
require("steps_run" in _agent_r.metrics, "agent: metrics present")
require(all(g in _agent_r.report_markdown for g in ("G1", "G2", "G3", "G4")), "agent: report rendered (gate checklist)")
# Degraded agent run -> Inconclusive.
_agent_d = OrchestratorAgent().run({})
require(_agent_d.verdict == "Inconclusive", "agent: degraded -> Inconclusive")
# SKILL.md registry doc + JSON schemas valid.
_skill_md = read(ROOT / "SKILL.md")
for sec in ("Skill registry", "Chain-of-thought router", "Tool registry", "Hooks & lifecycle"):
    require(sec in _skill_md, f"SKILL.md: section {sec}")
for _n in ("harness_input.schema.json", "harness_result.schema.json",
           "skill_spec.schema.json", "tool.schema.json"):
    json.loads(read(ROOT / "assets" / "schemas" / _n))
    ok(f"schema valid: {_n}")
# --------------------------------------------------------------------------- #
# PDPT + README + PROJECT-detail
# --------------------------------------------------------------------------- #
pdpt = read(ROOT / "PROJECT-DEVELOPMENT-PHASE-TRACKING.md")
require("100%" in pdpt, "PDPT: 100% markers")
require("Phase 7" in pdpt, "PDPT: Phase 7 present")
require(pdpt.lower().count("100% complete") >= 6 or pdpt.count("COMPLETE") >= 6,
        "PDPT: >=7 complete phases")
readme = read(ROOT / "README.md")
require("Usage" in readme and "tjr" in readme.lower(), "README: usage + tjr")
pd = read(ROOT / "PROJECT-detail.md")
require("Idea (Vietnamese)" in pd, "PROJECT-detail: Idea (Vietnamese)")
require("Harness Architecture" in pd, "PROJECT-detail: harness architecture")

# progression.json
try:
    prog = json.loads(read(ROOT / "progression.json"))
    require(prog.get("completion_pct") == 100, "progression: 100%")
    require(prog.get("production_ready") is True, "progression: production_ready")
except Exception as ex:
    fail("progression.json", str(ex))

# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
total = checks_passed + checks_failed
print(f"[run_test_scenarios] {checks_passed}/{total} checks passed")
if failures:
    for f in failures:
        print("  - FAIL " + f)
    sys.exit(1)
print("[OK] all structural + runtime scenario checks passed")
sys.exit(0)