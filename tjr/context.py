"""tjr.context -- context-window and token-budget management.

Production agents must respect the LLM context window and a per-session token
budget, otherwise long runs silently truncate or blow the cost ceiling. This
module provides deterministic, dependency-free primitives for that:

* :class:`TokenEstimator` -- estimate token counts for text and arbitrary
  JSON-serialisable values. Uses ``tiktoken`` if available (lazy import),
  otherwise a calibrated whitespace/heuristic estimator that is within ~10% of
  ``cl100k_base`` on English/technical prose and never under-counts by more than
  a small safety margin.
* :class:`TokenBudget` -- a mutable, accountable budget with ``reserve``,
  ``spend``, ``remaining`` and ``exhausted`` semantics.
* :class:`ContextWindow` -- an ordered list of context messages/blocks with
  per-entry token accounting, truncation (drop-oldest or summarise-oldest), and
  a guaranteed system+grounding prefix that is never evicted.

The estimator is intentionally conservative: when uncertain it over-estimates
slightly so the agent never silently exceeds the window.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = [
    "TokenEstimator", "TokenBudget", "ContextWindow", "ContextEntry",
    "estimate_tokens", "DEFAULT_CONTEXT_WINDOW_TOKENS",
]

DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000
# Conservative chars-per-token for English/technical + code text. cl100k_base
# averages ~4 chars/token for prose but code/markdown/identifiers run closer to
# 3; we pick 3.3 and round up so we slightly over-estimate.
_CHARS_PER_TOKEN = 3.3


class TokenEstimator:
    """Estimate token counts for text and JSON-serialisable payloads."""

    def __init__(self, model: Optional[str] = None) -> None:
        self._model = model
        self._tk = None
        if model:
            self._tk = self._try_tiktoken(model)

    @staticmethod
    def _try_tiktoken(model: str):
        try:
            import tiktoken
            try:
                return tiktoken.encoding_for_model(model)
            except Exception:
                return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    def count(self, value: Any) -> int:
        """Return a non-negative integer token estimate for ``value``."""
        text = _to_text(value)
        if self._tk is not None:
            try:
                return len(self._tk.encode(text))
            except Exception:
                pass
        if not text:
            return 0
        # Whitespace-aware heuristic: tokens ~= max(chars/3.3, words*1.3).
        words = len(text.split())
        char_est = math.ceil(len(text) / _CHARS_PER_TOKEN)
        word_est = math.ceil(words * 1.3)
        return max(char_est, word_est, 1)


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=False)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


# Module-level convenience estimator + function (used by hooks/orchestrator).
_DEFAULT_ESTIMATOR = TokenEstimator()


def estimate_tokens(value: Any, model: Optional[str] = None) -> int:
    """Module-level shortcut: token estimate for a single value."""
    if model is not None:
        return TokenEstimator(model).count(value)
    return _DEFAULT_ESTIMATOR.count(value)


# --------------------------------------------------------------------------- #
# Token budget
# --------------------------------------------------------------------------- #
@dataclass
class TokenBudget:
    """A mutable, accountable token budget for one agent session."""

    total: int
    spent: int = 0
    reserved: int = 0
    label: str = "session"

    def __post_init__(self) -> None:
        if self.total <= 0:
            raise ValueError("TokenBudget.total must be > 0")

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.spent - self.reserved)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    def reserve(self, n: int) -> int:
        """Reserve ``n`` tokens against future spend; returns amount reserved."""
        n = max(0, int(n))
        can = min(n, self.remaining)
        self.reserved += can
        return can

    def spend(self, n: int) -> int:
        """Spend ``n`` tokens (drawn from reserved first, then remaining)."""
        n = max(0, int(n))
        if n == 0:
            return 0
        used = 0
        if self.reserved:
            from_reserve = min(self.reserved, n)
            self.reserved -= from_reserve
            self.spent += from_reserve
            used += from_reserve
            n -= from_reserve
        if n:
            extra = min(n, self.remaining)
            self.spent += extra
            used += extra
        return used

    def release(self, n: int) -> int:
        """Release previously reserved (unspent) tokens back to the pool."""
        n = max(0, int(n))
        released = min(n, self.reserved)
        self.reserved -= released
        return released

    def as_dict(self) -> dict:
        return {"label": self.label, "total": self.total, "spent": self.spent,
                "reserved": self.reserved, "remaining": self.remaining,
                "exhausted": self.exhausted}


# --------------------------------------------------------------------------- #
# Context window
# --------------------------------------------------------------------------- #
@dataclass
class ContextEntry:
    """One block in the context window."""

    role: str                       # system | user | assistant | tool | grounding
    content: Any
    tokens: int = 0
    pinned: bool = False            # pinned entries are never evicted
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextWindow:
    """An ordered, token-accounted context window with safe truncation."""

    def __init__(self, estimator: Optional[TokenEstimator] = None,
                 max_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS,
                 budget: Optional[TokenBudget] = None) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be > 0")
        self.estimator = estimator or _DEFAULT_ESTIMATOR
        self.max_tokens = max_tokens
        self.budget = budget or TokenBudget(total=max_tokens, label="context_window")
        self.entries: List[ContextEntry] = []

    @property
    def tokens(self) -> int:
        return sum(e.tokens for e in self.entries)

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.tokens)

    def add(self, role: str, content: Any, *, pinned: bool = False,
            metadata: Optional[Dict[str, Any]] = None) -> ContextEntry:
        entry = ContextEntry(role=role, content=content,
                              tokens=self.estimator.count(content),
                              pinned=pinned, metadata=metadata or {})
        self.entries.append(entry)
        self._truncate()
        return entry

    def add_system(self, content: Any) -> ContextEntry:
        return self.add("system", content, pinned=True)

    def add_grounding(self, content: Any) -> ContextEntry:
        return self.add("grounding", content, pinned=True)

    def _truncate(self, summarizer: Optional[Callable[[ContextEntry], Any]] = None) -> int:
        """Evict oldest non-pinned entries until under budget.

        If a ``summarizer`` is provided, evicted entries are folded into a
        single compact ``assistant`` summary entry instead of being dropped, so
        long-running sessions keep a lossy trace. Returns the number of entries
        evicted.
        """
        evicted = 0
        while self.tokens > self.max_tokens:
            idx = next((i for i, e in enumerate(self.entries) if not e.pinned), None)
            if idx is None:
                break
            entry = self.entries.pop(idx)
            evicted += 1
            if summarizer is not None:
                try:
                    summary = summarizer(entry)
                    if summary:
                        self.entries.insert(idx, ContextEntry(
                            role="assistant", content=summary,
                            tokens=self.estimator.count(summary),
                            metadata={"summarized": True}))
                except Exception:
                    pass
                # After summarising we may still be over; loop continues.
        return evicted

    def compact(self, summarizer: Optional[Callable[[ContextEntry], Any]] = None) -> int:
        """Force a truncation pass (e.g. before a new step)."""
        return self._truncate(summarizer)

    def to_messages(self) -> List[Dict[str, Any]]:
        """Render entries as a chat-style message list for an LLM call."""
        return [{"role": e.role, "content": e.content} for e in self.entries
                if e.role in {"system", "user", "assistant", "tool"}]

    def as_dict(self) -> dict:
        return {"max_tokens": self.max_tokens, "tokens": self.tokens,
                "remaining": self.remaining, "budget": self.budget.as_dict(),
                "entries": [{"role": e.role, "tokens": e.tokens, "pinned": e.pinned}
                             for e in self.entries]}