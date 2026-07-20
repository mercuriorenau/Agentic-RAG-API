"""LLM listwise reranker for retrieved passages (fail-open)."""

from __future__ import annotations

import json
import re

from openai import AsyncOpenAI

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

RERANK_PROMPT = (
    "You rerank document passages for a retrieval system. "
    "Given a query and numbered passages, return ONLY a JSON array of passage "
    "indices ordered from most relevant to least relevant. "
    "Include every index exactly once. Example: [2, 0, 1]"
)


class LLMReranker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def rank_indices(self, query: str, passages: list[str]) -> list[int] | None:
        """Return passage indices best-first, or None to signal fail-open."""
        if len(passages) <= 1:
            return list(range(len(passages)))
        if not self.settings.openai_api_key:
            return None

        try:
            body = "\n\n".join(f"[{index}] {text[:800]}" for index, text in enumerate(passages))
            response = await self.client.chat.completions.create(
                model=self.settings.rerank_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": RERANK_PROMPT},
                    {"role": "user", "content": f"Query: {query}\n\nPassages:\n{body}"},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            return parse_index_list(content, expected=len(passages))
        except Exception:
            logger.exception("llm_rerank_failed")
            return None


def parse_index_list(content: str, *, expected: int) -> list[int]:
    match = re.search(r"\[[\s\d,]+\]", content)
    if not match:
        raise ValueError(f"No JSON array in rerank response: {content[:200]}")
    raw = json.loads(match.group(0))
    if not isinstance(raw, list):
        raise ValueError("Rerank response is not a list")
    indices = [int(item) for item in raw]
    seen: set[int] = set()
    cleaned: list[int] = []
    for index in indices:
        if 0 <= index < expected and index not in seen:
            cleaned.append(index)
            seen.add(index)
    for index in range(expected):
        if index not in seen:
            cleaned.append(index)
    return cleaned
