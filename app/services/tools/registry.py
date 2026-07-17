from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models import User
from app.schemas.query import Citation
from app.services.llm.base import ToolSpec
from app.services.rag_service import RAGService
from app.services.tools.web_search import web_search


@dataclass
class ToolContext:
    user: User
    rag_service: RAGService
    chat_id: UUID | None = None
    tavily_api_key: str = ""


@dataclass
class ToolResult:
    content: str
    citations: list[Citation] = field(default_factory=list)


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="retrieve_documents",
        description=(
            "Search the user's uploaded documents for passages relevant to the question. "
            "Use this when the answer likely depends on uploaded files."
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
            "document retrieval or web search."
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

    retrieved = await context.rag_service.retrieve(
        context.user,
        query,
        chat_id=context.chat_id,
    )
    if not retrieved:
        return ToolResult(content="No relevant passages found in uploaded documents.")

    blocks: list[str] = []
    citations: list[Citation] = []
    for item in retrieved:
        blocks.append(
            f"[{item.document.filename} | chunk {item.chunk.chunk_index}]\n{item.chunk.content}"
        )
        citations.append(
            Citation(
                source_type="document",
                document_id=str(item.document.id),
                document_name=item.document.filename,
                chunk_id=str(item.chunk.id),
                excerpt=item.chunk.content[:300],
                score=round(item.score, 4),
            )
        )
    return ToolResult(content="\n\n".join(blocks), citations=citations)


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
