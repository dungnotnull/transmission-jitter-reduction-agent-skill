"""tools/test_knowledge_updater.py — tests for tjr.knowledge_updater.

Validates hash dedup, scoring, entry formatting, append idempotency and the
KnowledgeUpdater orchestrator (against a temp brain file; no network).

Run: ``python tools/test_knowledge_updater.py`` (or via pytest).
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from tjr import knowledge_updater as ku  # noqa: E402


# ---- hash dedup ----
def test_hash():
    a = ku.compute_hash("https://x.com/1")
    b = ku.compute_hash("https://x.com/1")
    assert a == b
    assert ku.compute_hash("https://x.com/2") != a


def test_hash_case_and_whitespace_insensitive():
    assert ku.compute_hash("  HTTPS://X.COM/1 ") == ku.compute_hash("https://x.com/1")


# ---- scoring ----
def test_score():
    e = {"title": ku.KNOWLEDGE_CONFIG["domain"],
         "abstract": ku.KNOWLEDGE_CONFIG["domain"],
         "published_date": datetime.datetime.now(), "citation_count": 10}
    s = ku.score_entry(e, ku.KNOWLEDGE_CONFIG["keywords"], datetime.datetime.now())
    assert 0 <= s <= 10


def test_score_recency_decay():
    old = {"title": "network jitter reduction", "abstract": "",
           "published_date": datetime.datetime(2010, 1, 1), "citation_count": 0}
    new = {"title": "network jitter reduction", "abstract": "",
           "published_date": datetime.datetime.now(), "citation_count": 0}
    now = datetime.datetime.now()
    assert ku.score_entry(new, ku.KNOWLEDGE_CONFIG["keywords"], now) > \
           ku.score_entry(old, ku.KNOWLEDGE_CONFIG["keywords"], now)


def test_score_keyword_relevance():
    base = {"published_date": datetime.datetime.now(), "citation_count": 0}
    relevant = dict(base, title="FQ-CoDel AQM bufferbloat jitter WiFi QoS DSCP")
    irrelevant = dict(base, title="Completely unrelated topic about cooking recipes")
    now = datetime.datetime.now()
    assert ku.score_entry(relevant, ku.KNOWLEDGE_CONFIG["keywords"], now) > \
           ku.score_entry(irrelevant, ku.KNOWLEDGE_CONFIG["keywords"], now)


# ---- formatting ----
def test_format():
    txt = ku.format_entry({"title": "T", "authors": ["A"], "year": 2026, "venue": "V",
                           "doi_or_url": "https://x", "abstract": "ab"}, 5.0)
    assert "DOI/URL:" in txt and "Relevance Score:" in txt and "### " in txt


# ---- config sanity ----
def test_config_has_real_arxiv_categories():
    assert "cs.NI" in ku.KNOWLEDGE_CONFIG["arxiv_categories"]


def test_config_has_rss_feeds():
    assert len(ku.KNOWLEDGE_CONFIG["rss_feeds"]) >= 3


def test_config_scoring_weights_sum_to_one():
    w = ku.KNOWLEDGE_CONFIG["scoring_weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-9


# ---- append idempotency (temp brain, no network) ----
def _seed_brain(tmp_path: Path) -> Path:
    brain = tmp_path / "BRAIN.md"
    brain.write_text(
        "# Brain\n\n## 7. Knowledge Update Log\n",
        encoding="utf-8",
    )
    return brain


def test_append_then_dedup(tmp_path):
    brain = _seed_brain(tmp_path)
    entries = [{"title": "Paper A", "authors": ["X"], "year": 2026, "venue": "V",
                "doi_or_url": "https://example.com/a", "abstract": "network jitter",
                "published_date": datetime.datetime.now(), "citation_count": 5,
                "source": "test"}]
    n1 = ku.append_to_brain(entries, dry_run=False, brain_path=brain)
    assert n1 == 1
    # Re-append the same entry -> dedup, 0 new.
    n2 = ku.append_to_brain(entries, dry_run=False, brain_path=brain)
    assert n2 == 0
    assert brain.read_text(encoding="utf-8").count("Paper A") == 1


def test_append_respects_max_entries(tmp_path):
    brain = _seed_brain(tmp_path)
    entries = [{"title": f"P{i}", "authors": [], "year": 2026, "venue": "V",
                "doi_or_url": f"https://example.com/{i}", "abstract": "jitter",
                "published_date": datetime.datetime.now(), "citation_count": 0,
                "source": "test"} for i in range(50)]
    n = ku.append_to_brain(entries, dry_run=False, brain_path=brain)
    assert n == ku.KNOWLEDGE_CONFIG["max_new_entries_per_run"]


def test_knowledge_updater_dry_run_does_not_write(tmp_path):
    brain = _seed_brain(tmp_path)
    before = brain.read_text(encoding="utf-8")
    upd = ku.KnowledgeUpdater(brain_path=brain)
    # Force collect() to return synthetic entries (no network).
    entries = [{"title": "Synthetic", "authors": [], "year": 2026, "venue": "V",
                "doi_or_url": "https://example.com/synthetic", "abstract": "jitter",
                "published_date": datetime.datetime.now(), "citation_count": 0,
                "source": "test"}]
    n = ku.append_to_brain(entries, dry_run=True, brain_path=brain)
    assert n == 1
    assert brain.read_text(encoding="utf-8") == before


# ---- standalone runner ----
def test_hash_old_compatibility():
    # Backward-compat: the original simple test from v1.0.0 still passes.
    a = ku.compute_hash("https://x.com/1"); b = ku.compute_hash("https://x.com/1")
    assert a == b and ku.compute_hash("https://x.com/2") != a


def test_score_old_compatibility():
    e = {"title": ku.KNOWLEDGE_CONFIG["domain"], "abstract": ku.KNOWLEDGE_CONFIG["domain"],
         "published_date": datetime.datetime.now(), "citation_count": 10}
    s = ku.score_entry(e, ku.KNOWLEDGE_CONFIG["keywords"], datetime.datetime.now())
    assert 0 <= s <= 10


def test_format_old_compatibility():
    txt = ku.format_entry({"title": "T", "authors": ["A"], "year": 2026, "venue": "V",
                           "doi_or_url": "https://x", "abstract": "ab"}, 5.0)
    assert "DOI/URL:" in txt and "Relevance Score:" in txt


def _run_all() -> int:
    import inspect, tempfile, traceback
    failures = 0
    tmp = Path(tempfile.mkdtemp())
    for name, fn in list(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        kwargs = {}
        sig = inspect.signature(fn)
        if "tmp_path" in sig.parameters:
            kwargs["tmp_path"] = Path(tempfile.mkdtemp())
        try:
            fn(**kwargs)
            print(f"[OK] {name}")
        except Exception:
            print(f"[FAIL] {name}")
            traceback.print_exc()
            failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)