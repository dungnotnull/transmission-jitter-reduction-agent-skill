"""tjr.knowledge_updater â€” self-improving knowledge crawl pipeline.

Fetches the latest academic papers (ArXiv, Semantic Scholar) and domain news
(RSS) for the Network Jitter & Real-Time Transport Optimization domain, scores
them, de-duplicates against SECOND-KNOWLEDGE-BRAIN.md by SHA-256 of the
DOI/URL, and appends the highest-relevance new entries to Section 7.

Design goals (production-grade):

* Idempotent append (hash dedup) so cron re-runs are safe.
* Exponential backoff + rate-limit awareness for every HTTP call.
* Graceful degradation when a source is unreachable (one source failing must
  not abort the run).
* Structured logging + optional JSON output for CI / monitoring.
* Config-driven (KNOWLEDGE_CONFIG) so the same code crawls other domains.
* Zero hard dependency on optional packages: ``requests`` / ``feedparser`` are
  imported lazily and missing ones simply skip that source with a warning.

Public API (kept stable for the ``tools/`` shims and tests)::

    KNOWLEDGE_CONFIG, compute_hash, load_existing_hashes, score_entry,
    format_entry, fetch_with_retry, fetch_arxiv, fetch_semantic_scholar,
    fetch_rss, append_to_brain, KnowledgeUpdater, run

CLI: ``python -m tjr.knowledge_updater [--dry-run] [--news-only] [--json]``
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import requests
except ImportError:  # pragma: no cover - exercised only without requests
    requests = None  # type: ignore[assignment]
try:
    import feedparser
except ImportError:  # pragma: no cover
    feedparser = None  # type: ignore[assignment]

log = logging.getLogger("tjr.knowledge_updater")

BRAIN_PATH = Path(__file__).resolve().parent.parent / "SECOND-KNOWLEDGE-BRAIN.md"

# --------------------------------------------------------------------------- #
# Per-project crawl configuration
# --------------------------------------------------------------------------- #
KNOWLEDGE_CONFIG: Dict[str, Any] = {
    "domain": "Network Jitter & Real-Time Transport Optimization",
    "keywords": [
        "network jitter reduction",
        "AQM CoDel FQ-CoDel PIE CAKE",
        "bufferbloat diagnosis latency under load",
        "jitter buffer interpolation game netcode",
        "QoS DSCP traffic shaping gaming",
        "WiFi QoS WMM 802.11e gaming",
        "BBR congestion control realtime",
    ],
    # arXiv categories relevant to this domain:
    #   cs.NI  -> Networking and Internet Architecture
    #   eess.SP -> Signal Processing (real-time transport / queuing)
    #   cs.GT  -> Computer Science and Game Theory (online game networking)
    "arxiv_categories": ["cs.NI", "eess.SP", "cs.GT"],
    "arxiv_base": "https://export.arxiv.org/api/query",
    "semantic_scholar_base": "https://api.semanticscholar.org/graph/v1/paper/search",
    # Real, publicly available domain RSS feeds.
    "rss_feeds": [
        "https://www.rfc-editor.org/rdfco.ttl",  # RFC metadata (Turtle; parsed leniently)
        "https://news.openwrt.org/feed.xml",
        "https://www.bufferbloat.net/feed/",
        "https://blog.apnic.net/feed/",
        "https://networking.ifip.org/feed/",
    ],
    "authoritative_docs": [
        "IEEE/ACM Transactions on Networking",
        "Computer Networks (Elsevier)",
        "IEEE Communications Surveys & Tutorials",
        "Performance Evaluation (Elsevier)",
        "IEEE Transactions on Games",
        "Journal of Network and Computer Applications (Elsevier)",
        "IETF RFCs (8289 CoDel, 8290 FQ-CoDel, 8033 PIE, 8888 FQ-PIE, 9330 L4S)",
    ],
    "scoring_weights": {
        "recency": 0.4,
        "keyword_relevance": 0.4,
        "citation_count": 0.2,
    },
    "max_results_per_source": 10,
    "max_new_entries_per_run": 20,
    "request_timeout_s": 30,
    "max_retries": 3,
    "base_backoff_s": 2.0,
}


# --------------------------------------------------------------------------- #
# Dataclass for normalised entries
# --------------------------------------------------------------------------- #
@dataclass
class KnowledgeEntry:
    title: str
    authors: List[str]
    year: int
    venue: str
    doi_or_url: str
    abstract: str
    published_date: Optional[datetime]
    citation_count: int
    source: str
    score: float = 0.0

    def as_dict(self) -> dict:
        d = asdict(self)
        d["published_date"] = self.published_date.isoformat() if self.published_date else None
        return d


# --------------------------------------------------------------------------- #
# Hashing / dedup
# --------------------------------------------------------------------------- #
def compute_hash(identifier: str) -> str:
    """SHA-256 of the lowercased, stripped DOI/URL (case/whitespace-insensitive)."""
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()


_DOI_RE = re.compile(r"\*\*DOI/URL:\*\*\s*(\S+)")


def load_existing_hashes(brain_path: Optional[Path] = None) -> set:
    p = brain_path or BRAIN_PATH
    if not p.exists():
        return set()
    hashes: set = set()
    for m in _DOI_RE.finditer(p.read_text(encoding="utf-8")):
        hashes.add(compute_hash(m.group(1)))
    return hashes


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def score_entry(entry: Dict[str, Any], keywords: Sequence[str], now: datetime) -> float:
    """Composite 0-10 score = recency(0.4) + keyword_relevance(0.4) + citations(0.2)."""
    pub = entry.get("published_date")
    recency = 0.0
    if pub:
        try:
            days = (now - pub).days
            recency = max(0.0, 1.0 - days / 730.0)
        except Exception:
            recency = 0.0
    text = ((entry.get("title") or "") + " " + (entry.get("abstract") or "")).lower()
    # Token-level matching with partial credit: a keyword matches if its full
    # phrase appears, OR at least half of its distinctive tokens appear. This
    # makes relevance meaningful for short paper titles while still rewarding
    # exact-phrase hits more.
    hits = 0.0
    for kw in keywords:
        kwl = kw.lower()
        if kwl in text:
            hits += 1.0
            continue
        tokens = [t for t in re.split(r"\W+", kwl) if len(t) > 2]
        if not tokens:
            continue
        present = sum(1 for t in tokens if t in text)
        if present / len(tokens) >= 0.5:
            hits += present / len(tokens)
    relevance = min(hits / max(len(keywords), 1), 1.0)
    cit = int(entry.get("citation_count", 0) or 0)
    cit_score = min(math.log1p(cit) / math.log1p(1000), 1.0)
    w = KNOWLEDGE_CONFIG["scoring_weights"]
    return round((recency * w["recency"] + relevance * w["keyword_relevance"]
                  + cit_score * w["citation_count"]) * 10.0, 2)


# --------------------------------------------------------------------------- #
# HTTP with retry / backoff
# --------------------------------------------------------------------------- #
def fetch_with_retry(url: str, params: Optional[dict] = None,
                     max_retries: Optional[int] = None,
                     base_delay: Optional[float] = None,
                     timeout: Optional[float] = None):
    """GET with exponential backoff + 429/5xx retry. Returns a Response or None."""
    if requests is None:
        log.warning("requests not installed; skipping %s", url)
        return None
    retries = max_retries if max_retries is not None else int(KNOWLEDGE_CONFIG["max_retries"])
    delay = base_delay if base_delay is not None else float(KNOWLEDGE_CONFIG["base_backoff_s"])
    to = timeout if timeout is not None else float(KNOWLEDGE_CONFIG["request_timeout_s"])
    for attempt in range(retries):
        try:
            if attempt > 0:
                time.sleep(delay * (2 ** (attempt - 1)))
            resp = requests.get(url, params=params or {}, timeout=to,
                                headers={"User-Agent": "tjr-knowledge-updater/1.1"})
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", delay * (2 ** attempt)))
                log.warning("429 rate-limited on %s (attempt %d); sleeping %ss", url, attempt + 1, retry_after)
                if attempt < retries - 1:
                    time.sleep(min(retry_after, 60))
                    continue
                return None
            if resp.status_code >= 500:
                log.warning("server error %s on %s (attempt %d)", resp.status_code, url, attempt + 1)
                if attempt < retries - 1:
                    continue
                return None
            resp.raise_for_status()
            return resp
        except Exception as ex:
            log.warning("request failed attempt %d for %s: %s", attempt + 1, url, ex)
            if attempt >= retries - 1:
                return None
    return None


# --------------------------------------------------------------------------- #
# Source fetchers
# --------------------------------------------------------------------------- #
def fetch_arxiv(keywords: Sequence[str]) -> List[Dict[str, Any]]:
    if requests is None or not KNOWLEDGE_CONFIG["arxiv_categories"]:
        return []
    cats = KNOWLEDGE_CONFIG["arxiv_categories"]
    q = ("(" + " OR ".join("cat:" + c for c in cats) + ") AND ("
         + " OR ".join('"' + k + '"' for k in keywords[:5]) + ")")
    resp = fetch_with_retry(KNOWLEDGE_CONFIG["arxiv_base"], {
        "search_query": q, "sortBy": "submittedDate", "sortOrder": "descending",
        "max_results": KNOWLEDGE_CONFIG["max_results_per_source"],
    })
    if resp is None:
        return []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as ex:
        log.warning("arxiv xml parse error: %s", ex)
        return []
    out: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        t = entry.find("atom:title", ns); s = entry.find("atom:summary", ns)
        i = entry.find("atom:id", ns); p = entry.find("atom:published", ns)
        title = (t.text or "").strip().replace("\n", " ") if t is not None else ""
        url = (i.text or "").strip() if i is not None else ""
        if not title or not url:
            continue
        pub: Optional[datetime] = None
        if p is not None:
            try:
                from dateutil import parser as dp
                pub = dp.parse(p.text).replace(tzinfo=None)
            except Exception:
                pub = None
        authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)
                   if a.find("atom:name", ns) is not None][:3]
        out.append({
            "title": title, "authors": authors,
            "year": pub.year if pub else datetime.now().year,
            "venue": "ArXiv", "doi_or_url": url,
            "abstract": (s.text or "")[:300] if s is not None else "",
            "published_date": pub, "citation_count": 0, "source": "arxiv",
        })
    log.info("arxiv: %d entries", len(out))
    return out


def fetch_semantic_scholar(keywords: Sequence[str]) -> List[Dict[str, Any]]:
    if requests is None:
        return []
    resp = fetch_with_retry(KNOWLEDGE_CONFIG["semantic_scholar_base"], {
        "query": " ".join(keywords[:4]),
        "fields": "title,authors,year,venue,externalIds,abstract,citationCount",
        "limit": KNOWLEDGE_CONFIG["max_results_per_source"],
    })
    if resp is None:
        return []
    try:
        data = resp.json()
    except Exception as ex:
        log.warning("semantic scholar json error: %s", ex)
        return []
    out: List[Dict[str, Any]] = []
    for p in data.get("data", []):
        title = p.get("title", "")
        if not title:
            continue
        year = p.get("year") or datetime.now().year
        ext = p.get("externalIds", {}) or {}
        doi = ext.get("DOI") or (f"https://arxiv.org/abs/{ext['ArXiv']}" if ext.get("ArXiv") else "")
        if not doi:
            doi = "https://www.semanticscholar.org/paper/" + str(p.get("paperId", ""))
        out.append({
            "title": title,
            "authors": [a.get("name", "") for a in (p.get("authors", []) or [])[:3]],
            "year": year, "venue": p.get("venue") or "Unknown", "doi_or_url": doi,
            "abstract": (p.get("abstract") or "")[:300],
            "published_date": datetime(int(year), 1, 1) if year else datetime.now(),
            "citation_count": int(p.get("citationCount", 0) or 0),
            "source": "semantic_scholar",
        })
    log.info("semantic_scholar: %d entries", len(out))
    return out


def fetch_rss() -> List[Dict[str, Any]]:
    if feedparser is None or not KNOWLEDGE_CONFIG["rss_feeds"]:
        return []
    out: List[Dict[str, Any]] = []
    for url in KNOWLEDGE_CONFIG["rss_feeds"]:
        try:
            feed = feedparser.parse(url)
        except Exception as ex:
            log.warning("rss %s failed: %s", url, ex)
            continue
        for item in getattr(feed, "entries", [])[:10]:
            title = item.get("title", ""); link = item.get("link", "")
            if not title or not link:
                continue
            pp = item.get("published_parsed")
            pub = datetime(*pp[:6]) if pp else datetime.now()
            out.append({
                "title": title, "authors": ["Editorial"], "year": pub.year,
                "venue": "RSS", "doi_or_url": link,
                "abstract": (item.get("summary", ""))[:200],
                "published_date": pub, "citation_count": 0, "source": "rss",
            })
    log.info("rss: %d entries", len(out))
    return out


# --------------------------------------------------------------------------- #
# Formatting + append
# --------------------------------------------------------------------------- #
def format_entry(entry: Dict[str, Any], score: float) -> str:
    d = datetime.now().strftime("%Y-%m-%d")
    authors = ", ".join(entry.get("authors", [])) or "Unknown"
    return (
        "\n### " + d + " â€” " + entry.get("title", "Untitled") + "\n"
        "- **Authors:** " + authors + "\n"
        "- **Year:** " + str(entry.get("year", "")) + "\n"
        "- **Venue:** " + entry.get("venue", "Unknown") + "\n"
        "- **DOI/URL:** " + entry.get("doi_or_url", "") + "\n"
        "- **Relevance Score:** " + str(score) + "/10\n"
        "- **Key Finding:** " + entry.get("abstract", "No abstract available.") + "\n"
    )


def append_to_brain(entries: Sequence[Dict[str, Any]],
                    dry_run: bool = False,
                    brain_path: Optional[Path] = None) -> int:
    p = brain_path or BRAIN_PATH
    if not p.exists():
        log.error("brain file not found: %s", p)
        return 0
    existing = load_existing_hashes(p)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    new: List[Dict[str, Any]] = []
    for e in entries:
        doi = e.get("doi_or_url", "")
        if not doi:
            continue
        h = compute_hash(doi)
        if h in existing:
            continue
        existing.add(h)
        new.append(e)
    if not new:
        log.info("no new entries to append")
        return 0
    for e in new:
        e["_score"] = score_entry(e, KNOWLEDGE_CONFIG["keywords"], now)
    new.sort(key=lambda x: float(x["_score"]), reverse=True)
    new = new[: int(KNOWLEDGE_CONFIG["max_new_entries_per_run"])]
    text = "".join(format_entry(e, float(e["_score"])) for e in new)
    if dry_run:
        log.info("[dry-run] would append %d entries", len(new))
        return len(new)
    content = p.read_text(encoding="utf-8")
    if "## 7. Knowledge Update Log" in content:
        content = content + text
    else:
        content = content + "\n## 7. Knowledge Update Log\n" + text
    p.write_text(content, encoding="utf-8")
    log.info("appended %d entries", len(new))
    return len(new)


# --------------------------------------------------------------------------- #
# Orchestrator class (testable)
# --------------------------------------------------------------------------- #
class KnowledgeUpdater:
    """Object-oriented wrapper around the crawl pipeline (for tests/CI)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 brain_path: Optional[Path] = None) -> None:
        self.config = config or dict(KNOWLEDGE_CONFIG)
        self.brain_path = brain_path or BRAIN_PATH

    def collect(self, keywords: Sequence[str], news_only: bool = False) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        if not news_only:
            entries += fetch_arxiv(keywords)
            time.sleep(1)
            entries += fetch_semantic_scholar(keywords)
            time.sleep(1)
        entries += fetch_rss()
        return entries

    def update(self, keywords: Optional[Sequence[str]] = None,
               news_only: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        kw = list(keywords) if keywords else list(self.config["keywords"])
        entries = self.collect(kw, news_only)
        appended = append_to_brain(entries, dry_run=dry_run, brain_path=self.brain_path)
        return {
            "candidates": len(entries),
            "appended": appended,
            "dry_run": dry_run,
            "news_only": news_only,
            "brain_path": str(self.brain_path),
        }


def run(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="tjr knowledge crawl pipeline")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--news-only", action="store_true")
    ap.add_argument("--keywords", nargs="+", default=KNOWLEDGE_CONFIG["keywords"])
    ap.add_argument("--json", action="store_true", help="emit JSON summary instead of logs")
    args = ap.parse_args(argv)
    updater = KnowledgeUpdater()
    if args.json:
        # Silence logging for clean JSON.
        logging.getLogger().setLevel(logging.WARNING)
    result = updater.update(args.keywords, news_only=args.news_only, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[DONE] candidates={result['candidates']} appended={result['appended']}")
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()