"""tjr.skills -- skill registry, resolver, chain-of-thought router and validation.

This is the flexible, modular skill-registry core of the agent framework. A
*skill* is a self-contained, declarative capability with:

* ``name`` / ``description`` -- identity + routing signal.
* ``inputs_schema`` / ``outputs_schema`` -- JSON Schema (subset) describing the
  contract the skill honours (see SKILL.md).
* ``tools`` -- the names of registered tools the skill is allowed to invoke.
* ``quality_gates`` -- the gate ids the skill is responsible for satisfying.
* ``handler`` -- a deterministic callable ``(context, state) -> output`` that
  implements the skill body.

The :class:`SkillRegistry` registers, resolves (by name and by fuzzy keyword
match) and executes skills. Before execution the registry validates inputs
against ``inputs_schema``; after execution it validates outputs against
``outputs_schema``. Schema failures raise :class:`SkillError` *before* the
handler runs, and the result is wrapped in a :class:`SkillResult`.

The :class:`ChainOfThoughtRouter` produces a transparent reasoning trace and a
plan (ordered list of skill names) for a given query. The default plan mirrors
the 6-step harness contract (requirements -> evidence -> core analysis ->
knowledge -> advisor -> gate review) but the router can special-case short or
degraded inputs -- e.g. skip live-evidence steps when no measurements exist,
or short-circuit to an Inconclusive path when all inputs are missing. The trace
is returned alongside the plan so the orchestrator can log/expose the reasoning
(chain-of-thought transparency).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .logging_utils import get_logger
from .tools import _validate, ToolError  # reuse the JSON-schema subset validator

__all__ = [
    "SkillError", "SkillSpec", "SkillResult", "SkillRegistry",
    "ChainOfThoughtRouter", "RoutingPlan", "default_registry",
    "register_default_skills",
]

LOG = get_logger("skills")


class SkillError(ValueError):
    """Raised on skill registration/resolution/validation/execution failure."""


# --------------------------------------------------------------------------- #
# Skill spec + result
# --------------------------------------------------------------------------- #
SkillHandler = Callable[[Dict[str, Any], Dict[str, Any]], Any]


@dataclass
class SkillSpec:
    name: str
    description: str
    inputs_schema: Dict[str, Any]
    outputs_schema: Dict[str, Any]
    tools: Sequence[str] = ()
    quality_gates: Sequence[str] = ()
    handler: Optional[SkillHandler] = None
    step: int = 0  # 1-based position in the default 6-step plan.

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "step": self.step, "tools": list(self.tools),
                "quality_gates": list(self.quality_gates),
                "inputs_schema": self.inputs_schema,
                "outputs_schema": self.outputs_schema}


@dataclass
class SkillResult:
    ok: bool
    output: Any = None
    error: str = ""
    skill: str = ""
    duration_ms: float = 0.0

    def as_dict(self) -> dict:
        return {"ok": self.ok, "output": self.output, "error": self.error,
                "skill": self.skill, "duration_ms": self.duration_ms}


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
class SkillRegistry:
    """Register, resolve and execute skills with schema validation."""

    def __init__(self) -> None:
        self._skills: Dict[str, SkillSpec] = {}

    def register(self, spec: SkillSpec) -> None:
        if spec.name in self._skills:
            raise SkillError(f"skill already registered: {spec.name}")
        self._skills[spec.name] = spec

    def get(self, name: str) -> SkillSpec:
        if name not in self._skills:
            raise SkillError(f"unknown skill: {name}")
        return self._skills[name]

    def names(self) -> List[str]:
        return sorted(self._skills)

    def specs(self) -> Dict[str, dict]:
        return {n: s.as_dict() for n, s in self._skills.items()}

    def resolve(self, query: str) -> List[str]:
        """Fuzzy keyword resolution: return skill names whose description/keywords
        overlap the query tokens, ranked by overlap count."""
        if not query:
            return []
        qtokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        scored: List[tuple] = []
        for name, spec in self._skills.items():
            hay = (spec.name + " " + spec.description).lower()
            stokens = set(re.findall(r"[a-z0-9]+", hay))
            overlap = len(qtokens & stokens)
            if overlap:
                scored.append((overlap, spec.step, name))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [name for _, _, name in scored]

    def execute(self, name: str, context: Optional[Dict[str, Any]] = None,
                state: Optional[Dict[str, Any]] = None) -> SkillResult:
        import time
        context = context or {}
        state = state if state is not None else {}
        try:
            spec = self.get(name)
        except SkillError as ex:
            return SkillResult(ok=False, error=str(ex), skill=name)
        try:
            _validate(context, spec.inputs_schema or {}, f"$.{name}.inputs")
        except ToolError as ex:
            return SkillResult(ok=False, error=str(ex), skill=name)
        if spec.handler is None:
            return SkillResult(ok=False, error=f"skill {name} has no handler", skill=name)
        start = time.perf_counter()
        try:
            output = spec.handler(context, state)
            output = _normalise_skill(output)
            _validate(output, spec.outputs_schema or {}, f"$.{name}.outputs")
            return SkillResult(ok=True, output=output, skill=name,
                               duration_ms=round((time.perf_counter() - start) * 1000.0, 3))
        except SkillError as ex:
            return SkillResult(ok=False, error=str(ex), skill=name,
                               duration_ms=round((time.perf_counter() - start) * 1000.0, 3))
        except Exception as ex:  # graceful: never raise to the orchestrator
            return SkillResult(ok=False, error=f"{type(ex).__name__}: {ex}", skill=name,
                               duration_ms=round((time.perf_counter() - start) * 1000.0, 3))


def _normalise_skill(value: Any) -> Any:
    if hasattr(value, "as_dict") and callable(value.as_dict):
        return value.as_dict()
    if isinstance(value, list):
        return [_normalise_skill(v) for v in value]
    if isinstance(value, tuple):
        return [_normalise_skill(v) for v in value]
    if hasattr(value, "value") and not isinstance(value, (dict, list, str, int, float, bool, type(None))):
        return value.value
    return value


# --------------------------------------------------------------------------- #
# Chain-of-thought router
# --------------------------------------------------------------------------- #
@dataclass
class RoutingPlan:
    plan: List[str]
    trace: List[str]
    degraded: bool = False
    short_circuit: Optional[str] = None  # verdict/skill to short-circuit to.

    def as_dict(self) -> dict:
        return {"plan": self.plan, "trace": self.trace,
                "degraded": self.degraded, "short_circuit": self.short_circuit}


class ChainOfThoughtRouter:
    """Plan an ordered skill execution list with a transparent reasoning trace.

    The router is deterministic and side-effect free (no LLM call) so the plan
    is regression-testable. It special-cases:

    * Missing measurement data -> mark degraded and short-circuit the advisor
      to an ``Inconclusive`` path while still running knowledge + gate skills.
    * A purely informational query (``explain``/``what is``) -> run requirements
      + knowledge only (skip evidence-collection field work).
    """

    DEFAULT_PLAN = ["gather_requirements", "evidence_collector",
                    "core_analysis", "knowledge_updater", "advisor"]

    INFO_PATTERNS = ("explain", "what is", "what are", "define", "how does", "tell me about")

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def plan(self, context: Dict[str, Any]) -> RoutingPlan:
        query = (context.get("query") or "").lower()
        has_rtt = bool(context.get("rtt_samples"))
        has_load = context.get("idle_latency_ms") is not None and context.get("latency_under_load_ms") is not None
        has_meas = has_rtt and has_load
        has_evidence = bool(context.get("evidence"))
        has_kb = bool(context.get("knowledge_citations"))
        informational = any(p in query for p in self.INFO_PATTERNS)

        trace: List[str] = []
        plan: List[str] = []
        short_circuit: Optional[str] = None

        trace.append(f"Query tokens analysed; informational={informational}, "
                     f"has_measurements={has_meas}, has_evidence={has_evidence}, has_kb={has_kb}.")
        plan.append("gather_requirements")

        if informational and not has_meas:
            trace.append("Informational query with no measurements: skip live evidence field-work, "
                         "keep knowledge + advisor for an educational, evidence-graded answer.")
            plan.append("knowledge_updater")
            plan.append("advisor")
            return RoutingPlan(plan=plan, trace=trace, degraded=True,
                              short_circuit="Inconclusive")

        plan.append("evidence_collector")
        plan.append("core_analysis")
        plan.append("knowledge_updater")
        plan.append("advisor")

        if not has_meas and not has_evidence and not has_kb:
            trace.append("All measurement, live and knowledge-base sources unavailable -> "
                         "degradation Level 4; advisor short-circuits to Inconclusive.")
            return RoutingPlan(plan=plan, trace=trace, degraded=True,
                              short_circuit="Inconclusive")
        if not has_meas:
            trace.append("Measurement data missing but some context available -> degraded; "
                         "advisor will emit Inconclusive rather than fabricate numbers.")
            return RoutingPlan(plan=plan, trace=trace, degraded=True,
                              short_circuit="Inconclusive")
        if not has_evidence and not has_kb:
            trace.append("Live + knowledge-base sources unavailable -> degraded Level 2; "
                         "historical context only, advisor still concludes from measurements.")
            return RoutingPlan(plan=plan, trace=trace, degraded=True)
        if not has_evidence or not has_kb:
            trace.append("Some primary sources unavailable -> degraded Level 1; substituted "
                         "sources flagged inline.")
            return RoutingPlan(plan=plan, trace=trace, degraded=True)
        trace.append("All sources available -> full evidenced analysis (Level 0).")
        return RoutingPlan(plan=plan, trace=trace, degraded=False)


# --------------------------------------------------------------------------- #
# Default skills (thin deterministic handlers that read from context/state)
# --------------------------------------------------------------------------- #
def _h_gather_requirements(context, state):
    return {
        "object": context.get("object") or "home network jitter reduction",
        "scope": context.get("scope") or "home network / gamer",
        "timeframe": context.get("timeframe") or "current",
        "available_inputs": context.get("available_inputs") or {
            "rtt_samples": len(context.get("rtt_samples") or []),
            "upload_mbps": context.get("upload_mbps"),
            "download_mbps": context.get("download_mbps"),
            "game": context.get("game"),
        },
        "target_audience": context.get("audience") or "gamer",
        "language": context.get("language") or "en",
        "analysis_type": "combined",
    }


def _h_evidence_collector(context, state):
    return {
        "current_data": context.get("current_data") or {},
        "authoritative_docs": context.get("authoritative_docs") or [],
        "recent_news": context.get("recent_news") or [],
        "reference_benchmarks": context.get("reference_benchmarks") or [],
        "limitation": "live fetch delegated to the Claude sub-skill; harness uses supplied evidence",
    }


def _h_core_analysis(context, state):
    # The deterministic math is owned by tjr.harness.Harness; the agent skill
    # delegates to the orchestrator which calls the harness. Here we expose the
    # measurement summary the advisor needs, computed only when data is present.
    rtts = context.get("rtt_samples") or []
    idle = context.get("idle_latency_ms")
    lul = context.get("latency_under_load_ms")
    if not rtts or idle is None or lul is None:
        return {"degraded": True, "reason": "measurement data missing"}
    from . import jitter_analysis as ja
    report = ja.compute_jitter(rtts)
    bb = ja.bufferbloat_grade(lul, idle)
    return {
        "degraded": False,
        "jitter_ms": report.consecutive_jitter_ms,
        "mdev_ms": report.mdev_ms,
        "rtp_jitter_ms": report.rtp_jitter_ms,
        "pdv_ms": report.pdv_ms,
        "bufferbloat_grade": bb.grade,
        "bufferbloat_added_ms": bb.added_latency_ms,
    }


def _h_knowledge_updater(context, state):
    cits = context.get("knowledge_citations") or []
    return {
        "citations": cits,
        "coverage": "Strong" if len(cits) >= 3 else "Moderate" if cits else "Weak",
        "gaps": [] if cits else ["no domain citations in knowledge base; flag for crawl"],
    }


def _h_advisor(context, state):
    core = state.get("core_analysis") or _h_core_analysis(context, state)
    if core.get("degraded"):
        return {"verdict": "Inconclusive",
                "reason": "insufficient measurement data for a decisive verdict"}
    from . import jitter_analysis as ja
    verdict = ja.verdict_from_scorecard(
        jitter_ms=core["jitter_ms"],
        bufferbloat_grade_letter=core["bufferbloat_grade"],
        isp_limited=bool(context.get("isp_limited")),
        data_available=True,
    )
    return {"verdict": verdict.value,
            "jitter_ms": core["jitter_ms"],
            "bufferbloat_grade": core["bufferbloat_grade"]}


def register_default_skills(registry: SkillRegistry) -> SkillRegistry:
    registry.register(SkillSpec(
        name="gather_requirements", step=1,
        description="Clarify object, scope, timeframe, available inputs, audience, language.",
        inputs_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        outputs_schema={"type": "object", "required": ["object", "analysis_type"],
                        "properties": {"object": {"type": "string"},
                                       "analysis_type": {"type": "string"}}},
        tools=["detect_language"], quality_gates=["U4"], handler=_h_gather_requirements,
    ))
    registry.register(SkillSpec(
        name="evidence_collector", step=2,
        description="Fetch authoritative real-time + reference + academic evidence.",
        inputs_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        outputs_schema={"type": "object", "required": ["limitation"],
                        "properties": {"limitation": {"type": "string"}}},
        tools=[], quality_gates=["U1", "U3"], handler=_h_evidence_collector,
    ))
    registry.register(SkillSpec(
        name="core_analysis", step=3,
        description="Jitter/PDV/bufferbloat + AQM + QoS/DSCP + Wi-Fi + buffer sizing.",
        inputs_schema={"type": "object",
                       "properties": {"rtt_samples": {"type": "array"},
                                      "idle_latency_ms": {"type": "number"},
                                      "latency_under_load_ms": {"type": "number"}}},
        outputs_schema={"type": "object", "properties": {"degraded": {"type": "boolean"},
                       "jitter_ms": {"type": "number"}, "bufferbloat_grade": {"type": "string"}}},
        tools=["compute_jitter", "bufferbloat_grade", "aqm_recommend", "dscp_marking",
               "wifi_channel_recommend", "jitter_buffer_sizing", "generate_scenarios"],
        quality_gates=["G1", "G2", "G3", "G4"], handler=_h_core_analysis,
    ))
    registry.register(SkillSpec(
        name="knowledge_updater", step=4,
        description="Query the knowledge base; surface tier-labelled citations; flag gaps.",
        inputs_schema={"type": "object",
                       "properties": {"knowledge_citations": {"type": "array"}}},
        outputs_schema={"type": "object", "required": ["coverage"],
                        "properties": {"coverage": {"type": "string",
                                       "enum": ["Strong", "Moderate", "Weak"]}}},
        tools=[], quality_gates=["U1"], handler=_h_knowledge_updater,
    ))
    registry.register(SkillSpec(
        name="advisor", step=5,
        description="Synthesize a risk-disclosed conclusion + scenarios + evidence chain.",
        inputs_schema={"type": "object", "properties": {"isp_limited": {"type": "boolean"}}},
        outputs_schema={"type": "object", "required": ["verdict"],
                        "properties": {"verdict": {"type": "string",
                                       "enum": ["Low Jitter", "Conditional (ISP-limited)",
                                                "High Jitter", "Inconclusive"]}}},
        tools=["verdict_from_scorecard"], quality_gates=["U2", "U6"], handler=_h_advisor,
    ))
    return registry


def default_registry() -> SkillRegistry:
    reg = SkillRegistry()
    register_default_skills(reg)
    return reg