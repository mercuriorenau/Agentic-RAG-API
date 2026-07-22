"""Adaptive retrieval budget: scale top_k by query breadth, with a hard cap."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import Settings

# Broad / survey-style questions that need more passages (still capped).
_BROAD_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bcada\b",
        r"\btodos(?:\s+los)?\b",
        r"\btodas(?:\s+las)?\b",
        r"\ball\s+(?:the\s+)?(?:cases?|sections?|chapters?|items?)\b",
        r"\beach\s+(?:case|section|chapter)\b",
        r"\bevery\s+(?:case|section|chapter)\b",
        r"\blist(?:a)?\s+(?:all|todos|todas|every)\b",
        r"\boverview\b",
        r"\bsummary\s+of\s+(?:the\s+)?(?:document|pdf|file|report)\b",
        r"\bsummarize\s+(?:the\s+)?(?:document|pdf|file|report|everything)\b",
        r"\bresumen\s+(?:completo|del\s+documento|general)\b",
        r"\bde\s+qu[eé]\s+trata\s+cada\b",
        r"\bwhat\s+(?:is|are)\s+each\b",
        r"\bentire\s+document\b",
        r"\bwhole\s+(?:document|pdf|file)\b",
    )
)

_COMPARE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bcompar(?:e|a|ar|ison|ación)\b",
        r"\bdifference(?:s)?\s+between\b",
        r"\bdiferencia(?:s)?\s+entre\b",
        r"\bversus\b|\b\bvs\.?\b",
    )
)


@dataclass(frozen=True)
class RetrievalBudget:
    """Resolved retrieve budget for one question."""

    top_k: int
    top_k_base: int
    top_k_max: int
    ideal_top_k: int
    capped: bool


def query_looks_broad(question: str) -> bool:
    text = question.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _BROAD_PATTERNS)


def query_looks_comparative(question: str) -> bool:
    text = question.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _COMPARE_PATTERNS)


def resolve_retrieval_budget(question: str, settings: Settings) -> RetrievalBudget:
    """Pick top_k for this question. Always within [1, top_k_max]."""
    base = max(1, int(settings.top_k))
    cap = max(base, int(settings.top_k_max))

    if not settings.adaptive_top_k:
        top_k = min(base, cap)
        return RetrievalBudget(
            top_k=top_k,
            top_k_base=base,
            top_k_max=cap,
            ideal_top_k=top_k,
            capped=False,
        )

    if query_looks_broad(question):
        # Survey prompts want wider coverage than the demo cap allows.
        ideal = max(cap * 2, 16)
        return RetrievalBudget(
            top_k=cap,
            top_k_base=base,
            top_k_max=cap,
            ideal_top_k=ideal,
            capped=ideal > cap,
        )

    if query_looks_comparative(question):
        ideal = base + 2
        top_k = min(cap, ideal)
        return RetrievalBudget(
            top_k=top_k,
            top_k_base=base,
            top_k_max=cap,
            ideal_top_k=ideal,
            capped=ideal > cap,
        )

    top_k = min(base, cap)
    return RetrievalBudget(
        top_k=top_k,
        top_k_base=base,
        top_k_max=cap,
        ideal_top_k=top_k,
        capped=False,
    )


def resolve_top_k(question: str, settings: Settings) -> int:
    """Pick top_k for this question. Always within [1, top_k_max]."""
    return resolve_retrieval_budget(question, settings).top_k
