"""Self-RAG helpers: grade retrieved evidence and rewrite weak queries."""

from __future__ import annotations

import json
import re
from typing import Literal

from openai import AsyncOpenAI

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GradeLabel = Literal["sufficient", "partial", "irrelevant"]

GRADE_PROMPT = (
    "You grade whether retrieved passages can answer a query. "
    "Return ONLY JSON: {\"grade\": \"sufficient\"|\"partial\"|\"irrelevant\", "
    "\"reason\": \"short\"}. "
    "sufficient = passages clearly answer the query; "
    "partial = some useful signal but incomplete; "
    "irrelevant = passages do not help."
)

REWRITE_PROMPT = (
    "You rewrite a search query to improve document retrieval. "
    "Return ONLY JSON: {\"query\": \"...\"}. "
    "Use concrete keywords, synonyms, and document-style phrasing. "
    "Keep it under 30 words. Do not answer the question."
)


class SelfRAGHelper:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def grade_evidence(self, query: str, passages: list[str]) -> GradeLabel:
        if not passages:
            return "irrelevant"
        if not self.settings.openai_api_key:
            return "partial"

        try:
            body = "\n\n".join(f"[{i}] {text[:600]}" for i, text in enumerate(passages))
            response = await self.client.chat.completions.create(
                model=self.settings.rerank_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": GRADE_PROMPT},
                    {
                        "role": "user",
                        "content": f"Query: {query}\n\nPassages:\n{body}",
                    },
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            return parse_grade(content)
        except Exception:
            logger.exception("self_rag_grade_failed")
            return "partial"

    async def rewrite_query(self, query: str, passages: list[str]) -> str | None:
        if not self.settings.openai_api_key:
            return None
        try:
            sample = "\n".join(text[:200] for text in passages[:3]) if passages else "(none)"
            response = await self.client.chat.completions.create(
                model=self.settings.rerank_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": REWRITE_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Original query: {query}\n"
                            f"Sample retrieved text:\n{sample}"
                        ),
                    },
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            rewritten = parse_rewrite(content)
            if not rewritten or rewritten.lower().strip() == query.lower().strip():
                return None
            return rewritten
        except Exception:
            logger.exception("self_rag_rewrite_failed")
            return None


def parse_grade(content: str) -> GradeLabel:
    data = _extract_json_object(content)
    grade = str(data.get("grade", "")).lower().strip()
    if grade in {"sufficient", "partial", "irrelevant"}:
        return grade  # type: ignore[return-value]
    raise ValueError(f"Invalid grade in response: {content[:200]}")


def parse_rewrite(content: str) -> str:
    data = _extract_json_object(content)
    query = str(data.get("query", "")).strip()
    if not query:
        raise ValueError(f"Missing rewrite query: {content[:200]}")
    return query[:400]


def needs_retry(grade: GradeLabel) -> bool:
    return grade in {"irrelevant", "partial"}


def _extract_json_object(content: str) -> dict:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object in response: {content[:200]}")
    raw = json.loads(match.group(0))
    if not isinstance(raw, dict):
        raise ValueError("Expected a JSON object")
    return raw
