"""tjr.agents -- specialized sub-agents + orchestrator.

The agent layer composes the building blocks into a runnable, observable
multi-agent system:

* :class:`SubAgent` wraps one :class:`tjr.skills.SkillSpec` + the shared tool
  registry and hooks. It is the *specialized sub-agent* (one per skill).
* :class:`RouterAgent` wraps the :class:`tjr.skills.ChainOfThoughtRouter` and
  produces a transparent plan + reasoning trace.
* :class:`OrchestratorAgent` runs the full 6-step protocol: pre-flight language
  detection -> router plan -> dispatch each step to its sub-agent -> emit hooks
  (pre/post step, degradation, gate, deliver) -> delegate the authoritative
  deterministic core + gate enforcement to :class:`tjr.harness.Harness` -> merge
  the agent trace + metrics + token accounting into an :class:`AgentResult`.

The orchestrator never duplicates the RFC-graded math or the gate engine; it
reuses the proven ``tjr.harness.Harness`` for the deterministic result, and adds
the agent-framework concerns (routing, tools, hooks, context/token budgeting,
structured events) on top. This keeps a single source of truth for the decision
logic while satisfying production observability requirements.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .config import Settings, load_settings
from .context import ContextWindow, TokenEstimator, TokenBudget
from .harness import Harness, HarnessInput, HarnessResult, detect_language
from .hooks import HookManager, HookType, default_hooks
from .logging_utils import configure_logging, get_logger
from .skills import ChainOfThoughtRouter, RoutingPlan, SkillRegistry, SkillResult, default_registry
from .tools import ToolRegistry, default_registry as default_tool_registry

__all__ = [
    "SubAgent", "RouterAgent", "OrchestratorAgent", "AgentResult",
    "run_agent",
]

LOG = get_logger("agents")


# --------------------------------------------------------------------------- #
# Sub-agent
# --------------------------------------------------------------------------- #
class SubAgent:
    """A specialized sub-agent bound to one skill + the shared tool registry."""

    def __init__(self, skill_name: str, registry: SkillRegistry,
                 tools: ToolRegistry, hooks: HookManager) -> None:
        self.skill_name = skill_name
        self.registry = registry
        self.tools = tools
        self.hooks = hooks
        self.spec = registry.get(skill_name)

    def run(self, context: Dict[str, Any], state: Dict[str, Any]) -> SkillResult:
        self.hooks.emit(HookType.PRE_STEP, source=self.skill_name,
                        payload={"tools": list(self.spec.tools)}, state=state)
        result = self.registry.execute(self.skill_name, context, state)
        self.hooks.emit(HookType.POST_STEP, source=self.skill_name,
                        payload={"ok": result.ok, "output": result.output,
                                 "error": result.error}, state=state)
        if not result.ok:
            self.hooks.emit(HookType.ON_ERROR, source=self.skill_name,
                            payload={"error": result.error}, state=state)
        return result


# --------------------------------------------------------------------------- #
# Router agent
# --------------------------------------------------------------------------- #
class RouterAgent:
    """Produces a chain-of-thought plan + trace for a context."""

    def __init__(self, registry: SkillRegistry, hooks: HookManager) -> None:
        self.router = ChainOfThoughtRouter(registry)
        self.hooks = hooks

    def plan(self, context: Dict[str, Any], state: Dict[str, Any]) -> RoutingPlan:
        plan = self.router.plan(context)
        self.hooks.emit(HookType.ON_SKILL_RESOLVE, source="router",
                        payload={"plan": plan.plan, "degraded": plan.degraded,
                                 "short_circuit": plan.short_circuit}, state=state)
        if plan.degraded:
            self.hooks.emit(HookType.ON_DEGRADATION, source="router",
                            payload={"level": _level_from_plan(plan)}, state=state)
        return plan


def _level_from_plan(plan: RoutingPlan) -> int:
    if plan.short_circuit == "Inconclusive":
        return 4
    return 1


# --------------------------------------------------------------------------- #
# Agent result
# --------------------------------------------------------------------------- #
@dataclass
class AgentResult:
    verdict: str
    plan: List[str]
    trace: List[str]
    degraded: bool
    short_circuit: Optional[str]
    skill_results: List[dict]
    harness_result: dict
    metrics: Dict[str, Any]
    token_summary: Dict[str, Any]
    report_markdown: str

    def as_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=indent)


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class OrchestratorAgent:
    """Runs the full agent protocol and delegates the deterministic core."""

    DOMAIN = "Network Jitter & Real-Time Transport Optimization"
    VERSION = "1.2.0"

    def __init__(self, settings: Optional[Settings] = None,
                 skills: Optional[SkillRegistry] = None,
                 tools: Optional[ToolRegistry] = None,
                 hooks: Optional[HookManager] = None,
                 harness: Optional[Harness] = None) -> None:
        self.settings = settings or load_settings()
        if self.settings.logging:
            configure_logging(self.settings)
        self.estimator = TokenEstimator(self.settings.llm.model) if self.settings.features.token_accounting else TokenEstimator()
        self.skills = skills or default_registry()
        self.tools = tools or default_tool_registry()
        self.hooks = hooks or default_hooks(self.estimator if self.settings.features.token_accounting else None)
        self.harness = harness or Harness()
        self.router_agent = RouterAgent(self.skills, self.hooks)
        self.context_window = ContextWindow(
            estimator=self.estimator,
            max_tokens=self.settings.llm.context_window_tokens,
            budget=TokenBudget(total=self.settings.llm.session_token_budget, label="session"),
        )

    def run(self, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        context = context or {}
        state: Dict[str, Any] = {}
        if self.settings.features.token_accounting:
            state["token_budget"] = self.context_window.budget

        self.hooks.emit(HookType.SESSION_START, source="orchestrator",
                        payload={"domain": self.DOMAIN, "version": self.VERSION}, state=state)
        # Grounding: system prompt + domain contract pinned in the context window.
        self.context_window.add_system(self._system_prompt())
        self.context_window.add_grounding(self._grounding())

        # Pre-flight language detection.
        lang = detect_language(context.get("query") or "").value
        state["language"] = lang

        # Router plan.
        plan = self.router_agent.plan(context, state)
        # Short-circuit handling: if the router short-circuits to Inconclusive we
        # still run the planned skills (for the trace/metrics) but the advisor's
        # verdict is determined by the deterministic harness below.

        # Dispatch each planned skill to its sub-agent.
        skill_results: List[dict] = []
        for name in plan.plan:
            agent = SubAgent(name, self.skills, self.tools, self.hooks)
            # The context each skill sees: a filtered view of the run context.
            skill_ctx = self._skill_context(name, context, state, lang)
            res = agent.run(skill_ctx, state)
            skill_results.append({"skill": name, "ok": res.ok, "output": res.output,
                                  "error": res.error, "duration_ms": res.duration_ms})
            if res.ok and self.settings.features.token_accounting:
                self.context_window.add(role="tool" if name != "advisor" else "assistant",
                                        content={name: res.output})

        # Delegate the authoritative deterministic core + gate enforcement.
        hinput = self._to_harness_input(context, lang)
        hres = self.harness.run(hinput)
        self._emit_gate_events(hres, state)

        # Render + deliver hooks.
        self.hooks.emit(HookType.PRE_RENDER, source="orchestrator",
                        payload={"verdict": hres.verdict}, state=state)
        self.hooks.emit(HookType.POST_RENDER, source="orchestrator",
                        payload={"degradation_level": hres.degradation_level}, state=state)
        self.hooks.emit(HookType.PRE_DELIVER, source="orchestrator",
                        payload={"verdict": hres.verdict}, state=state)
        self.hooks.emit(HookType.POST_DELIVER, source="orchestrator",
                        payload={"verdict": hres.verdict}, state=state)
        self.hooks.emit(HookType.SESSION_END, source="orchestrator",
                        payload={"verdict": hres.verdict, "gates": hres.gate_summary.get("checklist")}, state=state)

        token_summary = self.context_window.budget.as_dict() if self.settings.features.token_accounting else {"enabled": False}
        metrics = state.get("metrics", {})
        return AgentResult(
            verdict=hres.verdict,
            plan=plan.plan,
            trace=plan.trace,
            degraded=plan.degraded,
            short_circuit=plan.short_circuit,
            skill_results=skill_results,
            harness_result=hres.as_dict(),
            metrics=metrics,
            token_summary=token_summary,
            report_markdown=hres.report_markdown,
        )

    # -- internals --------------------------------------------------------- #
    def _skill_context(self, name: str, context: Dict[str, Any], state: Dict[str, Any], lang: str) -> Dict[str, Any]:
        base = dict(context)
        base.setdefault("language", lang)
        # core_analysis/advisor read prior step outputs from state snapshots.
        return base

    def _to_harness_input(self, context: Dict[str, Any], lang: str) -> HarnessInput:
        known = {f for f in HarnessInput.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in context.items() if k in known}
        return HarnessInput.from_dict(clean)

    def _emit_gate_events(self, hres: HarnessResult, state: Dict[str, Any]) -> None:
        for gr in hres.gate_results:
            self.hooks.emit(HookType.ON_GATE, source=gr.get("gate_id", ""),
                            payload={"passed": gr.get("status") in ("passed", "auto_fixed"),
                                     "status": gr.get("status"), "limitation": gr.get("limitation", "")},
                            state=state)
        if hres.degradation_level >= 1:
            self.hooks.emit(HookType.ON_DEGRADATION, source="harness",
                            payload={"level": hres.degradation_level,
                                     "limitations": hres.limitations}, state=state)

    def _system_prompt(self) -> str:
        return (f"You are the transmission-jitter-reduction orchestrator for "
                f"{self.DOMAIN}. Run the 6-step evidence-graded protocol, satisfy "
                f"quality gates U1-U6 + G1-G4, and deliver a risk-disclosed, "
                f"traceable recommendation. Version {self.VERSION}.")

    def _grounding(self) -> str:
        return ("Grounding: RFC 3550 (RTP jitter), RFC 3393 (PDV), RFC 8289 (CoDel), "
                "RFC 8290 (FQ-CoDel), RFC 8033 (PIE), RFC 9330 (L4S), RFC 2474/3246/2597 "
                "(DSCP/WMM), IEEE 802.11e. Disclosure precedes recommendation.")


# --------------------------------------------------------------------------- #
# Convenience entry point (used by tjr-agent CLI)
# --------------------------------------------------------------------------- #
def run_agent(context: Optional[Dict[str, Any]] = None,
              settings: Optional[Settings] = None) -> AgentResult:
    return OrchestratorAgent(settings=settings).run(context)