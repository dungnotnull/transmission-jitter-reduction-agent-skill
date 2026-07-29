"""tjr.hooks -- lifecycle hooks, state synchronization and event emission.

The agent framework emits a well-defined stream of lifecycle events as it runs
the 6-step protocol. Hooks are small callables subscribed to those events; they
decouple cross-cutting concerns (logging, token accounting, state snapshots,
metrics, degradation notices) from the orchestrator logic.

Design
------
* :class:`HookType` -- the closed set of lifecycle events (pre/post step,
  on-error, on-degradation, on-gate, pre/post render, pre/post deliver, on
  tool call, on skill resolve).
* :class:`Event` -- a structured, immutable-ish event record.
* :class:`EventBus` -- subscribe/emit with per-handler exception isolation (one
  hook crashing never aborts the run; it is logged and disabled for the rest of
  the session so a broken hook cannot poison the whole pipeline).
* :class:`HookManager` -- convenience wrapper that owns an :class:`EventBus`
  plus the standard built-in hooks (structured logging, token accounting,
  state snapshot, metrics counters) wired from settings.

Hook handlers receive the :class:`Event` and the shared mutable ``state`` dict,
so they can synchronise state (e.g. record the verdict, accumulate token
spend) between steps without coupling the steps to each other.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .logging_utils import get_logger, log_event

__all__ = [
    "HookType", "Event", "EventHandler", "EventBus", "HookManager",
    "LoggingHook", "TokenAccountingHook", "StateSnapshotHook", "MetricsHook",
    "default_hooks",
]

LOG = get_logger("hooks")


class HookType(str, Enum):
    SESSION_START = "session.start"
    SESSION_END = "session.end"
    PRE_STEP = "step.pre"
    POST_STEP = "step.post"
    ON_ERROR = "error"
    ON_DEGRADATION = "degradation"
    ON_GATE = "gate"
    PRE_RENDER = "render.pre"
    POST_RENDER = "render.post"
    PRE_DELIVER = "deliver.pre"
    POST_DELIVER = "deliver.post"
    ON_TOOL = "tool.call"
    ON_SKILL_RESOLVE = "skill.resolve"


@dataclass
class Event:
    type: HookType
    payload: Dict[str, Any] = field(default_factory=dict)
    # Name of the emitting step/skill/tool, for traceability.
    source: str = ""

    def as_dict(self) -> dict:
        return {"type": self.type.value, "source": self.source, "payload": self.payload}


EventHandler = Callable[["Event", Dict[str, Any]], None]


class EventBus:
    """In-process event bus with exception-isolated handlers."""

    def __init__(self) -> None:
        self._handlers: Dict[HookType, List[EventHandler]] = {}
        self._disabled: set = set()  # id(handler) of handlers that errored out
        self._lock = threading.RLock()
        self._history: List[Event] = []

    def subscribe(self, event_type: HookType, handler: EventHandler) -> None:
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to every event type."""
        with self._lock:
            for t in HookType:
                self._handlers.setdefault(t, []).append(handler)

    def emit(self, event: Event, state: Optional[Dict[str, Any]] = None) -> Event:
        st = state if state is not None else {}
        with self._lock:
            self._history.append(event)
            handlers = list(self._handlers.get(event.type, []))
        for h in handlers:
            hid = id(h)
            if hid in self._disabled:
                continue
            try:
                h(event, st)
            except Exception as ex:  # isolate: never let a hook crash the run
                LOG.warning("hook disabled after error on %s: %s", event.type.value, ex,
                            extra={"event": event.type.value, "hook_error": str(ex)})
                with self._lock:
                    self._disabled.add(hid)
        return event

    def history(self, event_type: Optional[HookType] = None) -> List[Event]:
        with self._lock:
            if event_type is None:
                return list(self._history)
            return [e for e in self._history if e.type == event_type]

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


# --------------------------------------------------------------------------- #
# Built-in hooks
# --------------------------------------------------------------------------- #
class LoggingHook:
    """Emit every event as a structured log record."""

    def __init__(self, level: str = "INFO") -> None:
        self.level = level.lower()

    def __call__(self, event: Event, state: Dict[str, Any]) -> None:
        flat = _flatten(event.payload)
        # 'level' in a payload is domain data (e.g. degradation level), never a
        # log severity -- rename it so it does not clash with log_event's kwarg.
        if "level" in flat:
            flat["payload_level"] = flat.pop("level")
        log_event(LOG, event.type.value, level=self.level, source=event.source, **flat)


def _flatten(d: Dict[str, Any]) -> Dict[str, Any]:
    """One-level flatten of nested dicts for structured logging readability."""
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out[f"{k}.{k2}"] = v2
        else:
            out[k] = v
    return out


class TokenAccountingHook:
    """Spend the estimated tokens of step outputs against a token budget.

    The budget object is passed in the session ``state`` under
    ``"token_budget"`` (a :class:`tjr.context.TokenBudget`). If absent or the
    feature is disabled, this hook is a no-op.
    """

    def __init__(self, estimator) -> None:
        self.estimator = estimator

    def __call__(self, event: Event, state: Dict[str, Any]) -> None:
        if event.type != HookType.POST_STEP:
            return
        budget = state.get("token_budget")
        if budget is None:
            return
        output = event.payload.get("output")
        if output is None:
            return
        spent = self.estimator.count(output)
        budget.spend(spent)
        state.setdefault("token_spent", 0)
        state["token_spent"] = state.get("token_spent", 0) + spent
        log_event(LOG, "tokens.spend", level="DEBUG", step=event.source, tokens=spent,
                  remaining=budget.remaining)


class StateSnapshotHook:
    """Record selected step outputs into ``state`` for later steps to reuse.

    Useful for state synchronization: e.g. the core-analysis step's verdict is
    stored under ``state["verdict"]`` so the advisor step can read it without a
    direct call coupling.
    """

    def __init__(self, snapshot_keys: Dict[str, str]) -> None:
        # snapshot_keys: {step_name: state_key} -- store that step's output.
        self.snapshot_keys = snapshot_keys

    def __call__(self, event: Event, state: Dict[str, Any]) -> None:
        if event.type != HookType.POST_STEP:
            return
        state_key = self.snapshot_keys.get(event.source)
        if state_key is None:
            return
        if "output" in event.payload:
            state[state_key] = event.payload["output"]


class MetricsHook:
    """Accumulate simple counters/gauges into ``state["metrics"]``."""

    def __init__(self) -> None:
        self.metrics: Dict[str, Any] = {"steps_run": 0, "errors": 0,
                                        "degradations": 0, "gates_failed": 0,
                                        "tools_called": 0}

    def __call__(self, event: Event, state: Dict[str, Any]) -> None:
        if event.type == HookType.POST_STEP:
            self.metrics["steps_run"] += 1
        elif event.type == HookType.ON_ERROR:
            self.metrics["errors"] += 1
        elif event.type == HookType.ON_DEGRADATION:
            self.metrics["degradations"] += 1
        elif event.type == HookType.ON_GATE and not event.payload.get("passed", True):
            self.metrics["gates_failed"] += 1
        elif event.type == HookType.ON_TOOL:
            self.metrics["tools_called"] += 1
        state["metrics"] = dict(self.metrics)


# --------------------------------------------------------------------------- #
# Hook manager
# --------------------------------------------------------------------------- #
class HookManager:
    """Owns the event bus + the standard built-in hooks."""

    def __init__(self, estimator=None, *, enable_logging: bool = True,
                 enable_metrics: bool = True, snapshot_keys: Optional[Dict[str, str]] = None) -> None:
        self.bus = EventBus()
        self.metrics = MetricsHook()
        if enable_logging:
            self.bus.subscribe_all(LoggingHook())
        if enable_metrics:
            self.bus.subscribe_all(self.metrics)
        if estimator is not None:
            self.bus.subscribe(HookType.POST_STEP, TokenAccountingHook(estimator))
        if snapshot_keys:
            self.bus.subscribe(HookType.POST_STEP, StateSnapshotHook(snapshot_keys))

    def emit(self, event_type: HookType, source: str = "",
             payload: Optional[Dict[str, Any]] = None,
             state: Optional[Dict[str, Any]] = None) -> Event:
        ev = Event(type=event_type, source=source, payload=payload or {})
        self.bus.emit(ev, state if state is not None else {})
        return ev

    def history(self, event_type: Optional[HookType] = None) -> List[Event]:
        return self.bus.history(event_type)


def default_hooks(estimator=None) -> HookManager:
    """Return a HookManager with the production default hooks installed."""
    # snapshot_keys map {skill/source name -> state_key}: the StateSnapshotHook
    # stores that source's POST_STEP output under the state_key so later skills
    # can read prior outputs without direct coupling.
    return HookManager(estimator=estimator, enable_logging=True, enable_metrics=True,
                       snapshot_keys={
                           "gather_requirements": "requirements",
                           "evidence_collector": "evidence",
                           "core_analysis": "core_analysis",
                           "knowledge_updater": "knowledge",
                           "advisor": "advisor",
                       })