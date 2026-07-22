from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models import User
from app.schemas.query import Citation
from app.services.llm.base import ToolSpec
from app.services.rag_service import RAGService
from app.services.retrieval_budget import query_looks_broad, resolve_retrieval_budget
from app.services.tools.web_search import web_search


@dataclass
class ToolContext:
    user: User
    rag_service: RAGService
    chat_id: UUID | None = None
    tavily_api_key: str = ""
    user_question: str = ""


@dataclass
class ToolResult:
    content: str
    citations: list[Citation] = field(default_factory=list)
    retrieval_trace: list[dict] = field(default_factory=list)


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="retrieve_documents",
        description=(
            "Search the user's uploaded documents for passages relevant to the question. "
            "Use this when the answer likely depends on uploaded files. "
            "Prefer search queries that match the document language and concrete labels "
            "(e.g. 'Caso 1', company names) over abstract English paraphrases. "
            "Retrieval returns a small adaptive budget of chunks (not the whole file) "
            "to limit tokens — for long documents, prefer focused queries "
            "(one case/section) over 'list everything'. "
            "If it returns no relevant passages, tell the user the documents do not "
            "contain the answer instead of inventing document content."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query derived from the user question",
                }
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="web_search",
        description=(
            "Search the public web for current or general information not in uploaded documents. "
            "Use when the question needs live or external facts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Web search query",
                }
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="answer_directly",
        description=(
            "Signal that the question can be answered from general knowledge without "
            "document retrieval or web search. Do NOT use this when the chat has uploaded "
            "documents and the user is asking about those files, cases, or passages — "
            "use retrieve_documents instead."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief reason why a direct answer is appropriate",
                }
            },
            "required": ["reason"],
        },
    ),
]


async def execute_tool(
    name: str,
    arguments: dict[str, Any],
    context: ToolContext,
) -> ToolResult:
    if name == "retrieve_documents":
        return await _retrieve_documents(arguments, context)
    if name == "web_search":
        return await _web_search(arguments, context)
    if name == "answer_directly":
        reason = str(arguments.get("reason") or "General knowledge is sufficient.")
        return ToolResult(content=f"Direct answer approved. Reason: {reason}")
    return ToolResult(content=f"Unknown tool: {name}")


async def _retrieve_documents(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    query = str(arguments.get("query") or "").strip()
    if not query:
        return ToolResult(content="retrieve_documents requires a non-empty query.")

    user_question = (context.user_question or "").strip()
    budget_question = user_question or query
    # Broad surveys: search with the user's wording. Models often pass abstract English
    # tool queries ("case descriptions") that miss Spanish PDFs even when top_k is raised.
    if user_question and query_looks_broad(budget_question):
        search_query = user_question
    else:
        search_query = query

    result = await context.rag_service.retrieve(
        context.user,
        search_query,
        chat_id=context.chat_id,
        budget_question=budget_question,
    )
    trace = result.trace.to_dicts()
    budget = resolve_retrieval_budget(budget_question, context.rag_service.settings)
    weak_hit = len(result.chunks) < max(2, budget.top_k // 2)

    # Retry with the raw user question when the first pass under-fills the budget.
    if (
        weak_hit
        and user_question
        and user_question.casefold() != search_query.casefold()
    ):
        fallback = await context.rag_service.retrieve(
            context.user,
            user_question,
            chat_id=context.chat_id,
            budget_question=budget_question,
        )
        trace = trace + fallback.trace.to_dicts()
        if len(fallback.chunks) > len(result.chunks):
            result = fallback

    retrieved = result.chunks
    if not retrieved:
        return ToolResult(
            content=(
                "No relevant passages found in uploaded documents. "
                "Do not invent document content or citations. "
                "Tell the user the uploaded files do not appear to answer this question, "
                "or use web_search / answer_directly if appropriate. "
                "If the upload is not in English, retry retrieve_documents with "
                "document-language keywords (e.g. 'Caso 1', company names)."
            ),
            citations=[],
            retrieval_trace=trace,
        )

    blocks: list[str] = []
    citations: list[Citation] = []
    for item in retrieved:
        page = item.chunk.page_number
        page_label = f" | page {page}" if page is not None else ""
        blocks.append(
            f"[{item.document.filename} | chunk {item.chunk.chunk_index}{page_label}]\n"
            f"{item.chunk.content}"
        )
        citations.append(
            Citation(
                source_type="document",
                document_id=str(item.document.id),
                document_name=item.document.filename,
                chunk_id=str(item.chunk.id),
                page_number=page,
                excerpt=item.chunk.content[:300],
                score=round(item.score, 4),
            )
        )

    if len(trace) > 1:
        attempt_lines = [
            (
                f"- try {index + 1}: grade={item['grade']} "
                f"chunks={item['chunk_count']} query={item['query']}"
            )
            for index, item in enumerate(trace)
        ]
        blocks.insert(0, "Self-RAG retrieval attempts:\n" + "\n".join(attempt_lines))

    used = trace[-1] if trace else {}
    used_k = used.get("top_k")
    max_k = used.get("top_k_max") or context.rag_service.settings.top_k_max
    ideal_k = used.get("ideal_top_k")
    capped = bool(used.get("budget_capped"))
    candidate_count = used.get("candidate_count")
    rerank = used.get("rerank") or "skipped"
    budget_note = (
        f"Retrieval budget: returned {len(retrieved)} chunk(s)"
        + (f" with adaptive top_k={used_k}" if used_k else "")
        + f" (hard cap top_k_max={max_k}). "
    )
    if candidate_count is not None:
        budget_note += (
            f"Hybrid search kept {candidate_count} scored candidate(s) before the final cut. "
        )
    if rerank == "applied":
        budget_note += "LLM listwise rerank reordered those candidates, then sliced to top_k. "
    elif rerank == "fail_open":
        budget_note += (
            "Rerank was enabled but failed open — kept hybrid order, then sliced to top_k. "
        )
    elif rerank == "disabled":
        budget_note += "Rerank was off — kept hybrid RRF order, then sliced to top_k. "
    budget_note += (
        "This demo intentionally does not load the entire document into the model. "
    )
    if (
        capped
        and isinstance(ideal_k, int)
        and isinstance(used_k, int)
        and ideal_k > used_k
    ):
        budget_note += (
            f"This question would be better with about top_k={ideal_k} passages for fuller "
            f"coverage, but the demo capped retrieve at top_k={used_k}. "
            "Start your user-facing answer with a short caveat that this survey may omit "
            "sections because of that demo cap, then list only what the passages support. "
        )
    if query_looks_broad(query):
        budget_note += (
            "Broad questions may omit some sections — ask about one case or section "
            "for fuller coverage. Incomplete survey answers are a token-cost limit, "
            "not missing files."
        )
    else:
        budget_note += (
            "If a detail is missing, ask a narrower follow-up about that section."
        )
    blocks.append(budget_note)

    return ToolResult(content="\n\n".join(blocks), citations=citations, retrieval_trace=trace)


async def _web_search(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    query = str(arguments.get("query") or "").strip()
    if not query:
        return ToolResult(content="web_search requires a non-empty query.")

    results = await web_search(query, api_key=context.tavily_api_key)
    if results.get("unavailable"):
        return ToolResult(
            content=(
                "Web search is unavailable because TAVILY_API_KEY is not configured. "
                "Answer without live web results, or use retrieve_documents / answer_directly."
            )
        )
    if results.get("error"):
        return ToolResult(content=f"Web search failed: {results['error']}")

    items = results.get("results") or []
    if not items:
        return ToolResult(content="No web results found.")

    blocks: list[str] = []
    citations: list[Citation] = []
    for item in items:
        title = item.get("title") or "Web result"
        url = item.get("url") or ""
        snippet = item.get("content") or ""
        blocks.append(f"[{title}]({url})\n{snippet}")
        citations.append(
            Citation(
                source_type="web",
                document_name=title,
                excerpt=snippet[:300],
                url=url or None,
                score=item.get("score"),
            )
        )
    return ToolResult(content="\n\n".join(blocks), citations=citations)
