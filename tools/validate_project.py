"""tools/validate_project.py -- 8-File Contract validator for Skill 262.

Verifies that the project satisfies the library-wide 8-File Contract plus the
production-hardening additions (the ``tjr`` package, LICENSE, pyproject.toml,
progression.json) and the Phase-7 agent-framework additions (modular skill
registry, chain-of-thought router, tools, hooks, config, context, modular
directories, SKILL.md registry). Exits 0 on success, non-zero on failure.

Run::

    python tools/validate_project.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The 8-File Contract (library standard) + production-hardening + agent-framework extras.
REQUIRED_FILES = {
    # 8-File Contract
    "CLAUDE.md": "Skill identity + dev tasks",
    "PROJECT-detail.md": "Full technical spec",
    "PROJECT-DEVELOPMENT-PHASE-TRACKING.md": "Phase roadmap",
    "README.md": "Public docs",
    "SECOND-KNOWLEDGE-BRAIN.md": "Living knowledge base",
    "skills/main.md": "Harness entry point",
    "tools/knowledge_updater.py": "Crawl pipeline",
    "tools/run_test_scenarios.py": "Scenario validator",
    # Production-hardening extras
    "LICENSE": "MIT license",
    "pyproject.toml": "Packaging metadata",
    "progression.json": "Build progression marker",
    "requirements.txt": "Runtime deps",
    "tools/validate_project.py": "This validator",
    "tools/test_knowledge_updater.py": "Crawl unit tests",
    "tools/test_jitter_analysis.py": "Domain math tests",
    "tools/test_quality_gates.py": "Gate engine tests",
    "tjr/__init__.py": "Package init",
    "tjr/jitter_analysis.py": "Domain math core",
    "tjr/quality_gates.py": "Gate engine",
    "tjr/harness.py": "Reference orchestrator",
    "tjr/knowledge_updater.py": "Crawl implementation",
    "tjr/cli.py": "Harness CLI",
    "tjr/jitter_cli.py": "Jitter CLI",
    "tjr/knowledge_cli.py": "Knowledge CLI",
    "tests/test-scenarios.md": "Scenario definitions",
    "tests/TEST_RESULTS.md": "Test results",
    # Phase 7 -- agent framework + modular directories
    "SKILL.md": "Skill registry documentation",
    "tjr/config.py": "Type-safe configuration",
    "tjr/logging_utils.py": "Structured logging",
    "tjr/context.py": "Context window + token budget",
    "tjr/tools.py": "Tool registry (schemas + handlers)",
    "tjr/hooks.py": "Lifecycle hooks + event bus",
    "tjr/skills.py": "Skill registry + chain-of-thought router",
    "tjr/agents.py": "Sub-agents + orchestrator",
    "tjr/agent_cli.py": "tjr-agent CLI",
    "tools/test_agent_framework.py": "Agent framework tests",
    "config/default.toml": "Baseline config",
    "config/README.md": "Config docs",
    "references/README.md": "References index",
    "references/prompt-templates.md": "Prompt base-templates",
    "references/domain-guidelines.md": "Domain grounding",
    "references/evidence-hierarchy.md": "Evidence tiers",
    "references/rfc-index.md": "RFC/IEEE standard index",
    "assets/README.md": "Assets index",
    "assets/schemas/harness_input.schema.json": "Input JSON schema",
    "assets/schemas/harness_result.schema.json": "Result JSON schema",
    "assets/schemas/skill_spec.schema.json": "SkillSpec JSON schema",
    "assets/schemas/tool.schema.json": "Tool JSON schema",
    "assets/diagrams/architecture.mmd": "Architecture diagram",
    "assets/diagrams/harness-flow.mmd": "Harness flow diagram",
    "scripts/setup.py": "Local setup",
    "scripts/seed_knowledge.py": "Knowledge seeding",
    "scripts/ingest_measurements.py": "Measurement ingestion",
    "scripts/run_crawl.py": "Crawl runner",
    "scripts/validate.py": "Validation suite runner",
}

checks_passed = 0
checks_failed = 0
failures: list = []


def ok() -> None:
    global checks_passed
    checks_passed += 1


def fail(label: str, detail: str = "") -> None:
    global checks_failed
    checks_failed += 1
    failures.append(f"{label}: {detail}")


def require(cond: bool, label: str, detail: str = "") -> None:
    if cond:
        ok()
    else:
        fail(label, detail)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def main() -> int:
    # 1. File presence.
    for rel, _doc in REQUIRED_FILES.items():
        require((ROOT / rel).exists(), f"file present: {rel}")

    # 2. 5 sub-skills with frontmatter + required sections.
    skills = ROOT / "skills"
    expected_subs = {
        "sub-gather-requirements", "sub-evidence-collector", "sub-core-analysis",
        "sub-knowledge-updater", "sub-advisor",
    }
    subs = {p.stem for p in skills.glob("sub-*.md")}
    require(subs == expected_subs, "sub-skill set exact", f"got {subs}")
    fm = re.compile(r"^---\s*\n(.*?\n)---", re.S)
    for name in expected_subs:
        txt = read(skills / f"{name}.md")
        m = fm.search(txt)
        require(bool(m), f"{name}: frontmatter")
        if m:
            require("name:" in m.group(1) and "description:" in m.group(1),
                    f"{name}: name+description in frontmatter")
        for sec in ("Role & Persona", "Workflow", "Output Format", "Quality Gates"):
            require(sec in txt, f"{name}: section '{sec}'")
        require("Registry Binding" in txt, f"{name}: registry binding section")

    # 3. main.md harness sections.
    main_txt = read(skills / "main.md")
    for sec in ("Role & Persona", "Quality Gates", "Graceful Degradation",
                "Pre-Flight", "Harness Execution Protocol", "Output Format",
                "Agent Framework"):
        require(sec in main_txt, f"main.md: section '{sec}'")
    for g in ("U1", "U2", "U3", "U4", "U5", "U6", "G1", "G2", "G3", "G4"):
        require(g in main_txt, f"main.md: gate {g} present")

    # 4. SECOND-KNOWLEDGE-BRAIN.md structure + DOIs.
    brain = read(ROOT / "SECOND-KNOWLEDGE-BRAIN.md")
    for sec in ("## 1. Core", "## 4. Authoritative Data Sources",
                "## 6. Self-Update Protocol", "## 7. Knowledge Update Log",
                "Tier 1", "Tier 4"):
        require(sec in brain, f"brain: section '{sec}'")
    dois = re.findall(r"10\.\d{4,9}/[^\s|]+", brain)
    require(len(dois) >= 2, "brain: >=2 DOI-cited references", f"found {len(dois)}")
    rfcs = re.findall(r"RFC\s?\d{3,4}", brain, re.I)
    require(len(rfcs) >= 3, "brain: >=3 RFC references", f"found {len(rfcs)}")

    # 5. tjr package imports cleanly.
    try:
        sys.path.insert(0, str(ROOT))
        import tjr  # noqa: F401
        from tjr import (Harness, HarnessInput, jitter_analysis, quality_gates,
                         OrchestratorAgent, ToolRegistry, SkillRegistry,
                         ChainOfThoughtRouter, load_settings)  # noqa: F401
        ok()
    except Exception as ex:  # pragma: no cover
        fail("tjr import", str(ex))

    # 6. progression.json valid + 100%.
    try:
        prog = json.loads(read(ROOT / "progression.json"))
        require(prog.get("completion_pct") == 100, "progression: 100%")
        require(prog.get("production_ready") is True, "progression: production_ready")
        require(any(k.startswith("phase_7") for k in prog.get("phases", {})), "progression: phase_7 present")
    except Exception as ex:
        fail("progression.json", str(ex))

    # 7. pyproject metadata + agent entry points.
    pp = read(ROOT / "pyproject.toml")
    require("transmission-jitter-reduction" in pp, "pyproject: identity")
    require("tjr-agent" in pp and "tjr-harness" in pp, "pyproject: agent + harness entry points")
    require('version = "1.2.0"' in pp, "pyproject: version 1.2.0")

    # 8. PDPT marks all phases 100%.
    pdpt = read(ROOT / "PROJECT-DEVELOPMENT-PHASE-TRACKING.md")
    require("100%" in pdpt, "PDPT: 100% markers present")
    require("Phase 7" in pdpt, "PDPT: Phase 7 present")
    require(pdpt.count("COMPLETE") >= 7 or pdpt.lower().count("100% complete") >= 7,
            "PDPT: >=7 complete phases")

    # 9. Agent framework: registry has 5 skills + 9 tools + router.
    try:
        from tjr.skills import default_registry as default_skills
        from tjr.tools import default_registry as default_tools
        from tjr.agents import OrchestratorAgent
        sk = default_skills()
        require(set(sk.names()) == {"gather_requirements", "evidence_collector",
               "core_analysis", "knowledge_updater", "advisor"}, "skill registry: 5 skills")
        tl = default_tools()
        require(len(tl.names()) >= 9, "tool registry: >=9 tools", f"got {len(tl.names())}")
        # Router produces a plan + trace.
        from tjr.skills import ChainOfThoughtRouter
        p = ChainOfThoughtRouter(sk).plan({"query": "analyze jitter",
                                           "rtt_samples": [10, 12],
                                           "idle_latency_ms": 10,
                                           "latency_under_load_ms": 30,
                                           "evidence": [{}],
                                           "knowledge_citations": [{}]})
        require(p.plan == ["gather_requirements", "evidence_collector", "core_analysis",
                           "knowledge_updater", "advisor"], "router: full plan")
        require(len(p.trace) >= 1, "router: non-empty trace")
        # Orchestrator runs end-to-end.
        r = OrchestratorAgent().run({"query": "x", "rtt_samples": [1, 2, 3, 4],
                                      "idle_latency_ms": 1, "latency_under_load_ms": 2})
        require(r.verdict in {"Low Jitter", "Conditional (ISP-limited)",
               "High Jitter", "Inconclusive"}, "orchestrator: verdict in declared set")
        require("steps_run" in r.metrics, "orchestrator: metrics present")
    except Exception as ex:
        fail("agent framework runtime", str(ex))

    # 10. Config layering + JSON schemas valid.
    try:
        from tjr.config import load_settings, ConfigError
        s = load_settings()
        require(s.features.agent_framework is True, "config: feature flag loaded")
        require("1.2.0" in s.version, "config: version 1.2.0")
        for n in ("harness_input.schema.json", "harness_result.schema.json",
                  "skill_spec.schema.json", "tool.schema.json"):
            json.loads(read(ROOT / "assets" / "schemas" / n))
        ok()
    except Exception as ex:
        fail("config/schemas", str(ex))

    # 11. SKILL.md registry doc present + references modular dirs.
    skill_md = read(ROOT / "SKILL.md")
    for sec in ("Skill registry", "Chain-of-thought router", "Tool registry",
                "Hooks & lifecycle", "Configuration", "Input / output JSON schemas"):
        require(sec in skill_md, f"SKILL.md: section '{sec}'")
    require("references/" in skill_md and "assets/" in skill_md and "config/" in skill_md,
            "SKILL.md: references modular directories")

    # Report.
    total = checks_passed + checks_failed
    print(f"[validate_project] {checks_passed}/{total} checks passed")
    if failures:
        for f in failures:
            print("  - FAIL " + f)
        return 1
    print("[OK] 8-File Contract + production-hardening + agent-framework satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())