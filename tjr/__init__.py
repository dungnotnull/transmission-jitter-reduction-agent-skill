"""transmission-jitter-reduction (tjr) -- production tooling package.

This package contains the real, runnable implementation behind the
``transmission-jitter-reduction`` Claude skill:

* :mod:`tjr.jitter_analysis`  -- domain math (RFC 3550 jitter, PDV,
  bufferbloat grading, AQM / QoS / Wi-Fi / jitter-buffer recommendations,
  scenario + verdict engine).
* :mod:`tjr.quality_gates`    -- programmatic U1-U6 + G1-G4 gate engine.
* :mod:`tjr.harness`          -- Python reference orchestrator of the
  6-step skill protocol (language detection, degradation levels,
  gate enforcement, JSON + Markdown output).
* :mod:`tjr.knowledge_updater` -- self-improving knowledge crawl pipeline
  (ArXiv, Semantic Scholar, RSS) with SHA-256 dedup and composite scoring.
* :mod:`tjr.config`           -- type-safe layered configuration management.
* :mod:`tjr.logging_utils`    -- structured (JSON) logging.
* :mod:`tjr.context`          -- context-window + token-budget management.
* :mod:`tjr.tools`            -- tool registry (JSON-schema tools + handlers).
* :mod:`tjr.hooks`            -- lifecycle hooks + event bus.
* :mod:`tjr.skills`           -- skill registry + chain-of-thought router.
* :mod:`tjr.agents`           -- specialized sub-agents + orchestrator.
"""

from .jitter_analysis import (
    JitterReport,
    BufferbloatGrade,
    AQMRecommendation,
    QoSMarking,
    WiFiChannelRecommendation,
    JitterBufferRecommendation,
    Scenario,
    Verdict,
    compute_jitter,
    ping_mdev,
    rtp_jitter,
    packet_delay_variation,
    bufferbloat_grade,
    aqm_recommend,
    dscp_marking,
    wifi_channel_recommend,
    jitter_buffer_sizing,
    generate_scenarios,
    verdict_from_scorecard,
    load_rtt_samples,
)
from .quality_gates import GateEngine, GateResult, GateStatus
from .harness import Harness, HarnessInput, HarnessResult, Language
from .config import Settings, load_settings, ConfigError
from .context import TokenEstimator, TokenBudget, ContextWindow, estimate_tokens
from .tools import Tool, ToolRegistry, ToolResult, default_registry as default_tool_registry
from .hooks import HookManager, EventBus, HookType, Event, default_hooks
from .skills import (
    SkillSpec, SkillResult, SkillRegistry, ChainOfThoughtRouter,
    RoutingPlan, default_registry as default_skill_registry,
)
from .agents import SubAgent, RouterAgent, OrchestratorAgent, AgentResult, run_agent

__version__ = "1.2.0"
__all__ = [
    "__version__",
    "JitterReport", "BufferbloatGrade", "AQMRecommendation", "QoSMarking",
    "WiFiChannelRecommendation", "JitterBufferRecommendation", "Scenario",
    "Verdict", "compute_jitter", "ping_mdev", "rtp_jitter",
    "packet_delay_variation", "bufferbloat_grade", "aqm_recommend",
    "dscp_marking", "wifi_channel_recommend", "jitter_buffer_sizing",
    "generate_scenarios", "verdict_from_scorecard", "load_rtt_samples",
    "GateEngine", "GateResult", "GateStatus",
    "Harness", "HarnessInput", "HarnessResult", "Language",
    "Settings", "load_settings", "ConfigError",
    "TokenEstimator", "TokenBudget", "ContextWindow", "estimate_tokens",
    "Tool", "ToolRegistry", "ToolResult", "default_tool_registry",
    "HookManager", "EventBus", "HookType", "Event", "default_hooks",
    "SkillSpec", "SkillResult", "SkillRegistry", "ChainOfThoughtRouter",
    "RoutingPlan", "default_skill_registry",
    "SubAgent", "RouterAgent", "OrchestratorAgent", "AgentResult", "run_agent",
]