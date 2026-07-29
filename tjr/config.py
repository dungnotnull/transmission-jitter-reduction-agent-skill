"""tjr.config -- type-safe configuration management.

Centralised, validated configuration for the whole transmission-jitter-reduction
toolkit: environment variables, LLM parameters, system-wide feature flags, and
overrides for the knowledge crawl pipeline. No third-party dependency is
required: configuration is loaded from environment variables and (optionally)
a TOML file, then validated by an explicit, pure-Python schema.

Design goals
------------
* **Type-safe**: every setting has a declared type and is coerced/validated on
  load; invalid values raise a clear ``ConfigError`` instead of failing later.
* **Layered**: defaults < TOML file (``config/default.toml``) < environment
  variables < explicit ``overrides`` argument. Each layer overrides the one
  below it.
* **Feature flags**: a typed ``FeatureFlags`` block gates optional behaviour
  (agent framework, chain-of-thought router, structured logging, token
  accounting, knowledge crawl) so operators can enable/disable subsystems
  without code changes.
* **LLM parameters**: model name, temperature, max tokens, retry/backoff and a
  token budget live in a dedicated block used by :mod:`tjr.context`.
* **Serializable**: ``Settings.as_dict``/``to_json`` round-trip the whole
  configuration for reproducible runs and CI logging.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ConfigError", "FeatureFlags", "LLMSettings", "CrawlSettings",
    "LoggingSettings", "Settings", "load_settings", "coerce_bool",
    "coerce_int", "coerce_float", "load_toml",
]

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "default.toml"


class ConfigError(ValueError):
    """Raised when configuration values are missing, wrong type or invalid."""


# --------------------------------------------------------------------------- #
# Primitive coercion helpers (strings from env/files -> typed values)
# --------------------------------------------------------------------------- #
_BOOL_TRUE = {"1", "true", "yes", "on", "y", "t"}
_BOOL_FALSE = {"0", "false", "no", "off", "n", "f", ""}


def coerce_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        raise ConfigError(f"{name}: missing boolean value")
    s = str(value).strip().lower()
    if s in _BOOL_TRUE:
        return True
    if s in _BOOL_FALSE:
        return False
    raise ConfigError(f"{name}: invalid boolean {value!r} (true/false/1/0/yes/no)")


def coerce_int(value: Any, name: str, *, minimum: Optional[int] = None,
               maximum: Optional[int] = None) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{name}: boolean is not a valid int")
    if isinstance(value, int):
        i = value
    elif isinstance(value, float) and value.is_integer():
        i = int(value)
    else:
        try:
            i = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{name}: invalid int {value!r}") from exc
    if minimum is not None and i < minimum:
        raise ConfigError(f"{name}: {i} < minimum {minimum}")
    if maximum is not None and i > maximum:
        raise ConfigError(f"{name}: {i} > maximum {maximum}")
    return i


def coerce_float(value: Any, name: str, *, minimum: Optional[float] = None,
                 maximum: Optional[float] = None) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{name}: boolean is not a valid float")
    if isinstance(value, (int, float)):
        f = float(value)
    else:
        try:
            f = float(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{name}: invalid float {value!r}") from exc
    if not _is_finite(f):
        raise ConfigError(f"{name}: non-finite value {value!r}")
    if minimum is not None and f < minimum:
        raise ConfigError(f"{name}: {f} < minimum {minimum}")
    if maximum is not None and f > maximum:
        raise ConfigError(f"{name}: {f} > maximum {maximum}")
    return f


def _is_finite(v: float) -> bool:
    import math
    return not (math.isnan(v) or math.isinf(v))


def coerce_str(value: Any, name: str, *, choices: Optional[Iterable[str]] = None) -> str:
    if value is None:
        raise ConfigError(f"{name}: missing string value")
    s = str(value).strip()
    if not s:
        raise ConfigError(f"{name}: empty string")
    if choices is not None and s not in choices:
        raise ConfigError(f"{name}: {s!r} not in {sorted(choices)}")
    return s


from typing import Iterable  # noqa: E402  (kept after helpers for locality)


# --------------------------------------------------------------------------- #
# Settings dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class FeatureFlags:
    """System-wide feature flags (all default on in production)."""

    agent_framework: bool = True
    chain_of_thought_router: bool = True
    structured_logging: bool = True
    token_accounting: bool = True
    hooks_event_bus: bool = True
    tools_registry: bool = True
    knowledge_crawl: bool = True
    bilingual_output: bool = True
    graceful_degradation: bool = True
    auto_fix_gates: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class LLMSettings:
    """LLM parameters + token budget for the agent framework.

    The toolkit is runnable without an LLM (the deterministic core in
    :mod:`tjr.jitter_analysis` and :mod:`tjr.harness`), but the agent layer
    still respects these parameters when an LLM is in the loop.
    """

    model: str = "claude-sonnet-4.5"
    temperature: float = 0.2
    max_output_tokens: int = 4096
    context_window_tokens: int = 200000
    request_timeout_s: int = 60
    max_retries: int = 3
    base_backoff_s: float = 2.0
    session_token_budget: int = 250000

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class CrawlSettings:
    """Overrides for the knowledge crawl pipeline (see tjr.knowledge_updater)."""

    max_results_per_source: int = 10
    max_new_entries_per_run: int = 20
    request_timeout_s: int = 30
    max_retries: int = 3
    base_backoff_s: float = 2.0

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class LoggingSettings:
    """Structured logging configuration."""

    level: str = "INFO"            # DEBUG|INFO|WARNING|ERROR|CRITICAL
    format: str = "json"           # json|text
    output: str = "stderr"         # stderr|stdout|<file path>

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Settings:
    """The fully-resolved, validated configuration object."""

    domain: str = "Network Jitter & Real-Time Transport Optimization"
    version: str = "1.2.0"
    environment: str = "production"   # development|staging|production
    language_default: str = "en"     # en|vi
    features: FeatureFlags = field(default_factory=FeatureFlags)
    llm: LLMSettings = field(default_factory=LLMSettings)
    crawl: CrawlSettings = field(default_factory=CrawlSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    def as_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=indent)


# --------------------------------------------------------------------------- #
# TOML loader (stdlib tomllib on 3.11+, vendored fallback otherwise)
# --------------------------------------------------------------------------- #
def load_toml(path: Path) -> Dict[str, Any]:
    """Load a TOML file into a dict.

    Uses the stdlib ``tomllib`` on Python 3.11+. On older interpreters a tiny
    subset parser handles the flat ``[section]`` / ``key = value`` files used by
    ``config/default.toml``; unsupported constructs raise ``ConfigError`` so
    operators are never silently misconfigured.
    """
    path = Path(path)
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib  # type: ignore[import-not-found]
        return tomllib.loads(text)
    except ModuleNotFoundError:
        return _toml_subset_parser(text)


def _toml_subset_parser(text: str) -> Dict[str, Any]:
    """Minimal TOML subset parser: [sections], key = value, strings/ints/floats/bools."""
    out: Dict[str, Any] = {}
    section: Optional[str] = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            out[section] = {}
            continue
        if "=" not in line:
            raise ConfigError(f"TOML line {lineno}: expected 'key = value', got {raw!r}")
        key, _, val = line.partition("=")
        key = key.strip().strip('"')
        val = val.strip()
        parsed = _toml_value(val, lineno)
        if section is None:
            out[key] = parsed
        else:
            out[section][key] = parsed
    return out


def _toml_value(val: str, lineno: int) -> Any:
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1]
    if val.lower() in {"true", "false"}:
        return val.lower() == "true"
    if re.fullmatch(r"-?\d+", val):
        return int(val)
    if re.fullmatch(r"-?\d+\.\d+", val):
        return float(val)
    raise ConfigError(f"TOML line {lineno}: unsupported value {val!r}")


# --------------------------------------------------------------------------- #
# Layered loader
# --------------------------------------------------------------------------- #
def _get(layer: Dict[str, Any], section: str, key: str, default: Any) -> Any:
    """Fetch layer[section][key], then layer[key], then default."""
    if section in layer and isinstance(layer[section], dict) and key in layer[section]:
        return layer[section][key]
    if key in layer:
        return layer[key]
    return default


def _env_layer() -> Dict[str, Any]:
    """Collect ``TJR_*`` environment variables into a layered dict.

    Naming convention: ``TJR_<SECTION>_<KEY>`` (uppercased), e.g.
    ``TJR_LLM_TEMPERATURE`` -> llm.temperature. Top-level keys use
    ``TJR_<KEY>`` (e.g. ``TJR_ENVIRONMENT``). Boolean/int/float coercion is
    performed during validation, not here.
    """
    env: Dict[str, Any] = {}
    sections = {"FEATURES": "features", "LLM": "llm", "CRAWL": "crawl", "LOGGING": "logging"}
    for k, v in os.environ.items():
        if not k.startswith("TJR_"):
            continue
        rest = k[4:]
        parts = rest.split("_", 1)
        if len(parts) == 2 and parts[0] in sections:
            section = sections[parts[0]]
            env.setdefault(section, {})[parts[1].lower()] = v
        else:
            env[rest.lower()] = v
    return env


def load_settings(path: Optional[Path] = None,
                  overrides: Optional[Dict[str, Any]] = None) -> Settings:
    """Build a validated :class:`Settings` from layered sources.

    Precedence (low -> high): dataclass defaults < TOML file < env vars < overrides.
    """
    toml = load_toml(path or DEFAULT_CONFIG_PATH)
    env = _env_layer()
    ovr = overrides or {}

    def pick(section: str, key: str, default: Any) -> Any:
        val = _get(ovr, section, key, None)
        if val is None:
            val = _get(env, section, key, None)
        if val is None:
            val = _get(toml, section, key, default)
        return val

    features = FeatureFlags(
        agent_framework=coerce_bool(pick("features", "agent_framework", True), "features.agent_framework"),
        chain_of_thought_router=coerce_bool(pick("features", "chain_of_thought_router", True), "features.chain_of_thought_router"),
        structured_logging=coerce_bool(pick("features", "structured_logging", True), "features.structured_logging"),
        token_accounting=coerce_bool(pick("features", "token_accounting", True), "features.token_accounting"),
        hooks_event_bus=coerce_bool(pick("features", "hooks_event_bus", True), "features.hooks_event_bus"),
        tools_registry=coerce_bool(pick("features", "tools_registry", True), "features.tools_registry"),
        knowledge_crawl=coerce_bool(pick("features", "knowledge_crawl", True), "features.knowledge_crawl"),
        bilingual_output=coerce_bool(pick("features", "bilingual_output", True), "features.bilingual_output"),
        graceful_degradation=coerce_bool(pick("features", "graceful_degradation", True), "features.graceful_degradation"),
        auto_fix_gates=coerce_bool(pick("features", "auto_fix_gates", True), "features.auto_fix_gates"),
    )
    llm = LLMSettings(
        model=coerce_str(pick("llm", "model", "claude-sonnet-4.5"), "llm.model"),
        temperature=coerce_float(pick("llm", "temperature", 0.2), "llm.temperature", minimum=0.0, maximum=2.0),
        max_output_tokens=coerce_int(pick("llm", "max_output_tokens", 4096), "llm.max_output_tokens", minimum=1),
        context_window_tokens=coerce_int(pick("llm", "context_window_tokens", 200000), "llm.context_window_tokens", minimum=1),
        request_timeout_s=coerce_int(pick("llm", "request_timeout_s", 60), "llm.request_timeout_s", minimum=1),
        max_retries=coerce_int(pick("llm", "max_retries", 3), "llm.max_retries", minimum=0),
        base_backoff_s=coerce_float(pick("llm", "base_backoff_s", 2.0), "llm.base_backoff_s", minimum=0.0),
        session_token_budget=coerce_int(pick("llm", "session_token_budget", 250000), "llm.session_token_budget", minimum=1),
    )
    crawl = CrawlSettings(
        max_results_per_source=coerce_int(pick("crawl", "max_results_per_source", 10), "crawl.max_results_per_source", minimum=1),
        max_new_entries_per_run=coerce_int(pick("crawl", "max_new_entries_per_run", 20), "crawl.max_new_entries_per_run", minimum=1),
        request_timeout_s=coerce_int(pick("crawl", "request_timeout_s", 30), "crawl.request_timeout_s", minimum=1),
        max_retries=coerce_int(pick("crawl", "max_retries", 3), "crawl.max_retries", minimum=0),
        base_backoff_s=coerce_float(pick("crawl", "base_backoff_s", 2.0), "crawl.base_backoff_s", minimum=0.0),
    )
    logging = LoggingSettings(
        level=coerce_str(pick("logging", "level", "INFO"), "logging.level",
                         choices={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}),
        format=coerce_str(pick("logging", "format", "json"), "logging.format",
                          choices={"json", "text"}),
        output=coerce_str(pick("logging", "output", "stderr"), "logging.output"),
    )
    return Settings(
        domain=coerce_str(pick("", "domain", "Network Jitter & Real-Time Transport Optimization"), "domain"),
        version=coerce_str(pick("", "version", "1.2.0"), "version"),
        environment=coerce_str(pick("", "environment", "production"), "environment",
                              choices={"development", "staging", "production"}),
        language_default=coerce_str(pick("", "language_default", "en"), "language_default",
                                    choices={"en", "vi"}),
        features=features,
        llm=llm,
        crawl=crawl,
        logging=logging,
    )