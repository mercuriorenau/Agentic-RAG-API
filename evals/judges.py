"""LLM-as-judge scorers for faithfulness and answer relevance."""

from __future__ import annotations

import json
import re

from openai import AsyncOpenAI

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

JUDGE_PROMPT = (
    "You are an evaluation judge for a RAG system. "
    "Return ONLY JSON with keys faithfulness and answer_relevance, each a float 0-1. "
    "faithfulness = fraction of answer claims supported by the context (1 if no context needed). "
    "answer_relevance = how well the answer addresses the question."
)


async def judge_answer(
    question: str,
    answer: str,
    context_excerpts: list[str],
    *,
    settings: Settings | None = None,
) -> dict[str, float]:
    cfg = settings or get_settings()
    if not cfg.openai_api_key:
        return {"faithfulness": 0.0, "answer_relevance": 0.0}

    context = "\n\n".join(context_excerpts) if context_excerpts else "(no context)"
    try:
        client = AsyncOpenAI(api_key=cfg.openai_api_key)
        response = await client.chat.completions.create(
            model=cfg.rerank_model,
            temperature=0,
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\n"
                        f"Answer: {answer}\n\n"
                        f"Context:\n{context}"
                    ),
                },
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        return parse_judge_scores(content)
    except Exception:
        logger.exception("llm_judge_failed")
        return {"faithfulness": 0.0, "answer_relevance": 0.0}


def parse_judge_scores(content: str) -> dict[str, float]:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object in judge response: {content[:200]}")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Judge response must be a JSON object")
    faithfulness = float(data.get("faithfulness", 0))
    relevance = float(data.get("answer_relevance", 0))
    return {
        "faithfulness": max(0.0, min(1.0, faithfulness)),
        "answer_relevance": max(0.0, min(1.0, relevance)),
    }
