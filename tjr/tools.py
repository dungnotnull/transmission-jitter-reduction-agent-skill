"""tjr.tools -- rich tool definitions (schemas + execution handlers).

A tool is a strongly-typed, callable capability an agent can invoke dynamically.
Each tool declares:

* ``name`` / ``description`` -- for routing and prompting.
* ``input_schema`` / ``output_schema`` -- JSON Schema (draft 2020-12 subset)
  describing the accepted arguments and returned payload.
* ``handler`` -- a pure, deterministic Python callable that executes the tool.

The :class:`ToolRegistry` resolves tools by name, validates arguments against
their schema before execution, and validates the result against the output
schema. Validation is a self-contained subset of JSON Schema (type, required,
enum, minimum/maximum, items, properties) -- enough to enforce the tool
contracts without pulling a third-party validator. Schema failures raise a
``ToolError`` *before* the handler runs, so malformed agent calls never produce
silent garbage.

Built-in tools wrap :mod:`tjr.jitter_analysis` and :mod:`tjr.harness` so the
agent framework can reuse the RFC-graded deterministic core as first-class
tools.
"""
from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import jitter_analysis as ja
from .harness import detect_language, Language

__all__ = [
    "ToolError", "Tool", "ToolResult", "ToolRegistry",
    "default_registry", "register_default_tools",
]

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ToolError(ValueError):
    """Raised on schema-validation or execution failure of a tool."""


# --------------------------------------------------------------------------- #
# Tool dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    handler: Callable[..., Any]
    # Optional: declare positional/named arg names the handler expects.
    arg_names: Sequence[str] = ()

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "input_schema": self.input_schema, "output_schema": self.output_schema,
                "arg_names": list(self.arg_names)}


@dataclass
class ToolResult:
    ok: bool
    value: Any = None
    error: str = ""
    tool: str = ""
    duration_ms: float = 0.0

    def as_dict(self) -> dict:
        return {"ok": self.ok, "value": self.value, "error": self.error,
                "tool": self.tool, "duration_ms": self.duration_ms}


# --------------------------------------------------------------------------- #
# JSON-schema (subset) validator
# --------------------------------------------------------------------------- #
def _validate(value: Any, schema: Dict[str, Any], path: str = "$") -> None:
    """Validate ``value`` against a JSON-schema subset. Raises ToolError."""
    if not isinstance(schema, dict):
        return
    t = schema.get("type")
    if t is not None:
        _check_type(value, t, path)
    if "enum" in schema and value not in schema["enum"]:
        raise ToolError(f"{path}: {value!r} not in enum {schema['enum']!r}")
    if "const" in schema and value != schema["const"]:
        raise ToolError(f"{path}: {value!r} != const {schema['const']!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ToolError(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ToolError(f"{path}: {value} > maximum {schema['maximum']}")
    if "minItems" in schema and isinstance(value, list) and len(value) < schema["minItems"]:
        raise ToolError(f"{path}: fewer than {schema['minItems']} items")
    if "maxItems" in schema and isinstance(value, list) and len(value) > schema["maxItems"]:
        raise ToolError(f"{path}: more than {schema['maxItems']} items")
    if "minLength" in schema and isinstance(value, str) and len(value) < schema["minLength"]:
        raise ToolError(f"{path}: string shorter than {schema['minLength']}")
    if "required" in schema and isinstance(value, dict):
        for r in schema["required"]:
            if r not in value:
                raise ToolError(f"{path}: missing required property {r!r}")
    if "properties" in schema and isinstance(value, dict):
        for k, sub in schema["properties"].items():
            if k in value:
                _validate(value[k], sub, f"{path}.{k}")
    if "items" in schema and isinstance(value, list):
        for i, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{i}]")


_TYPES = {"string": str, "integer": int, "number": (int, float),
          "boolean": bool, "array": list, "object": dict, "null": type(None)}


def _check_type(value: Any, t: Any, path: str) -> None:
    if isinstance(t, list):
        for opt in t:
            try:
                _check_type(value, opt, path)
                return
            except ToolError:
                continue
        raise ToolError(f"{path}: {value!r} not any of {t}")
    exp = _TYPES.get(t)
    if exp is None:
        return
    if t == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ToolError(f"{path}: expected integer, got {type(value).__name__}")
    elif t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ToolError(f"{path}: expected number, got {type(value).__name__}")
    elif t == "null":
        if value is not None:
            raise ToolError(f"{path}: expected null")
    else:
        if not isinstance(value, exp) or (t == "boolean" and not isinstance(value, bool)):
            raise ToolError(f"{path}: expected {t}, got {type(value).__name__}")


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
class ToolRegistry:
    """Resolve and execute tools by name with schema validation."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ToolError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"unknown tool: {name}")
        return self._tools[name]

    def names(self) -> List[str]:
        return sorted(self._tools)

    def schemas(self) -> Dict[str, dict]:
        return {n: t.as_dict() for n, t in self._tools.items()}

    def execute(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Validate arguments, run the handler, validate the result."""
        import time
        arguments = arguments or {}
        try:
            tool = self.get(name)
        except ToolError as ex:
            return ToolResult(ok=False, error=str(ex), tool=name)
        try:
            _validate(arguments, tool.input_schema or {}, f"$.{name}.args")
        except ToolError as ex:
            return ToolResult(ok=False, error=str(ex), tool=name)
        start = time.perf_counter()
        try:
            value = tool.handler(**arguments) if isinstance(arguments, dict) else tool.handler(arguments)
            value = _normalise(value)
            _validate(value, tool.output_schema or {}, f"$.{name}.result")
            return ToolResult(ok=True, value=value, tool=name,
                              duration_ms=round((time.perf_counter() - start) * 1000.0, 3))
        except Exception as ex:  # graceful: never raise to the caller
            return ToolResult(ok=False, error=f"{type(ex).__name__}: {ex}", tool=name,
                              duration_ms=round((time.perf_counter() - start) * 1000.0, 3))


def _normalise(value: Any) -> Any:
    """Make dataclass / enum / tuple results JSON-serialisable."""
    if hasattr(value, "as_dict") and callable(value.as_dict):
        return value.as_dict()
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, tuple):
        return [_normalise(v) for v in value]
    if hasattr(value, "value"):  # Enum
        return value.value
    return value


# --------------------------------------------------------------------------- #
# Built-in tools (wrap the RFC-graded deterministic core)
# --------------------------------------------------------------------------- #
_RTT_ARRAY = {"type": "array", "minItems": 1, "items": {"type": "number", "minimum": 0}}


def _t_compute_jitter(rtts, timestamps_ms=None):
    return ja.compute_jitter(rtts, timestamps_ms)


def _t_bufferbloat(latency_under_load_ms, idle_latency_ms):
    return ja.bufferbloat_grade(latency_under_load_ms, idle_latency_ms)


def _t_aqm(upload_mbps=None, download_mbps=None, flow_count=1, link_type="generic"):
    return ja.aqm_recommend(upload_mbps, download_mbps, flow_count, link_type)


def _t_dscp(traffic_class="game", game=None):
    return ja.dscp_marking(traffic_class, game)


def _t_wifi(band="5", scans=None, width_mhz=80):
    scans = scans or []
    aps = [ja.APScan(**s) for s in scans]
    return ja.wifi_channel_recommend(band, aps, width_mhz)


def _t_jitter_buffer(jitter_ms, tickrate_hz, safety_factor=1.5):
    return ja.jitter_buffer_sizing(jitter_ms, tickrate_hz, safety_factor)


def _t_scenarios(rtts, idle_latency_ms, latency_under_load_ms):
    return ja.generate_scenarios(rtts, idle_latency_ms, latency_under_load_ms)


def _t_verdict(jitter_ms, bufferbloat_grade_letter, isp_limited=False, data_available=True):
    return ja.verdict_from_scorecard(jitter_ms, bufferbloat_grade_letter, isp_limited, data_available)


def _t_language(text):
    return {"language": detect_language(text or "").value}


def register_default_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register the built-in deterministic tools on ``registry``."""
    registry.register(Tool(
        name="detect_language",
        description="Pre-flight language detection (en/vi) from a user query.",
        input_schema={"type": "object", "required": ["text"],
                      "properties": {"text": {"type": "string", "minLength": 0}}},
        output_schema={"type": "object", "required": ["language"],
                       "properties": {"language": {"type": "string", "enum": ["en", "vi"]}}},
        handler=_t_language, arg_names=("text",),
    ))
    registry.register(Tool(
        name="compute_jitter",
        description="Compute the full jitter report (RFC 3550 jitter, mdev, PDV) over RTT samples (ms).",
        input_schema={"type": "object", "required": ["rtts"],
                      "properties": {"rtts": _RTT_ARRAY,
                                     "timestamps_ms": {"type": "array", "items": {"type": "number"}}}},
        output_schema={"type": "object", "required": ["n", "mean_ms", "consecutive_jitter_ms"],
                       "properties": {"n": {"type": "integer"}, "mean_ms": {"type": "number"},
                                      "consecutive_jitter_ms": {"type": "number"}}},
        handler=_t_compute_jitter, arg_names=("rtts", "timestamps_ms"),
    ))
    registry.register(Tool(
        name="bufferbloat_grade",
        description="Grade added latency under load (A-F) per the RFC 8289 / DSLReports scale.",
        input_schema={"type": "object", "required": ["latency_under_load_ms", "idle_latency_ms"],
                      "properties": {"latency_under_load_ms": {"type": "number", "minimum": 0},
                                     "idle_latency_ms": {"type": "number", "minimum": 0}}},
        output_schema={"type": "object", "required": ["grade", "added_latency_ms"],
                       "properties": {"grade": {"type": "string", "enum": ["A", "B", "C", "D", "F"]},
                                      "added_latency_ms": {"type": "number"}}},
        handler=_t_bufferbloat, arg_names=("latency_under_load_ms", "idle_latency_ms"),
    ))
    registry.register(Tool(
        name="aqm_recommend",
        description="Recommend an AQM algorithm (FQ-CoDel / CAKE) + 95% shaper config.",
        input_schema={"type": "object",
                      "properties": {"upload_mbps": {"type": "number", "minimum": 0},
                                     "download_mbps": {"type": "number", "minimum": 0},
                                     "flow_count": {"type": "integer", "minimum": 1},
                                     "link_type": {"type": "string"}}},
        output_schema={"type": "object", "required": ["algorithm"],
                       "properties": {"algorithm": {"type": "string", "enum": ["FQ-CoDel", "CAKE"]},
                                      "target_ms": {"type": "number"}}},
        handler=_t_aqm, arg_names=("upload_mbps", "download_mbps", "flow_count", "link_type"),
    ))
    registry.register(Tool(
        name="dscp_marking",
        description="Return the DSCP / WMM QoS marking for a traffic class (optional game ports).",
        input_schema={"type": "object",
                      "properties": {"traffic_class": {"type": "string"},
                                     "game": {"type": ["string", "null"]}}},
        output_schema={"type": "object", "required": ["dscp", "dscp_name", "wmm_ac"],
                       "properties": {"dscp": {"type": "integer"},
                                      "dscp_name": {"type": "string"}, "wmm_ac": {"type": "string"}}},
        handler=_t_dscp, arg_names=("traffic_class", "game"),
    ))
    registry.register(Tool(
        name="wifi_channel_recommend",
        description="Pick the least-congested preferred Wi-Fi channel for a band.",
        input_schema={"type": "object",
                      "properties": {"band": {"type": "string", "enum": ["2.4", "5", "6"]},
                                     "scans": {"type": "array", "items": {"type": "object"}},
                                     "width_mhz": {"type": "integer", "minimum": 20}}},
        output_schema={"type": "object", "required": ["channel", "band"],
                       "properties": {"channel": {"type": "integer"}, "band": {"type": "string"}}},
        handler=_t_wifi, arg_names=("band", "scans", "width_mhz"),
    ))
    registry.register(Tool(
        name="jitter_buffer_sizing",
        description="Recommend an interpolation/jitter-buffer depth in game ticks.",
        input_schema={"type": "object", "required": ["jitter_ms", "tickrate_hz"],
                      "properties": {"jitter_ms": {"type": "number", "minimum": 0},
                                     "tickrate_hz": {"type": "integer", "minimum": 1},
                                     "safety_factor": {"type": "number", "minimum": 0}}},
        output_schema={"type": "object", "required": ["buffer_ticks", "buffer_ms"],
                       "properties": {"buffer_ticks": {"type": "integer"},
                                      "buffer_ms": {"type": "number"}}},
        handler=_t_jitter_buffer, arg_names=("jitter_ms", "tickrate_hz", "safety_factor"),
    ))
    registry.register(Tool(
        name="generate_scenarios",
        description="Derive Best/Base/Worst jitter scenarios from measurements.",
        input_schema={"type": "object",
                      "required": ["rtts", "idle_latency_ms", "latency_under_load_ms"],
                      "properties": {"rtts": _RTT_ARRAY,
                                     "idle_latency_ms": {"type": "number", "minimum": 0},
                                     "latency_under_load_ms": {"type": "number", "minimum": 0}}},
        output_schema={"type": "array", "minItems": 3, "maxItems": 3,
                       "items": {"type": "object", "required": ["name", "jitter_ms"],
                                 "properties": {"name": {"type": "string"},
                                                "jitter_ms": {"type": "number"}}}},
        handler=_t_scenarios, arg_names=("rtts", "idle_latency_ms", "latency_under_load_ms"),
    ))
    registry.register(Tool(
        name="verdict_from_scorecard",
        description="Map a measurement scorecard to one of the 4 declared verdicts.",
        input_schema={"type": "object", "required": ["jitter_ms", "bufferbloat_grade_letter"],
                      "properties": {"jitter_ms": {"type": "number", "minimum": 0},
                                     "bufferbloat_grade_letter": {"type": "string", "enum": ["A", "B", "C", "D", "F"]},
                                     "isp_limited": {"type": "boolean"},
                                     "data_available": {"type": "boolean"}}},
        output_schema={"type": "string",
                       "enum": ["Low Jitter", "Conditional (ISP-limited)", "High Jitter", "Inconclusive"]},
        handler=_t_verdict,
        arg_names=("jitter_ms", "bufferbloat_grade_letter", "isp_limited", "data_available"),
    ))
    return registry


def default_registry() -> ToolRegistry:
    """Return a fresh ToolRegistry with all built-in tools registered."""
    reg = ToolRegistry()
    register_default_tools(reg)
    return reg