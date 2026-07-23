from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.rag_service import RetrievalAttempt, RetrievalResult, RetrievalTrace
from app.services.tools.registry import ToolContext, execute_tool


def _empty_trace(query: str = "q") -> RetrievalTrace:
    return RetrievalTrace(
        attempts=[
            RetrievalAttempt(query=query, grade="irrelevant", chunk_count=0, top_k=5, top_k_max=8)
        ],
        final_query=query,
        top_k=5,
    )


@pytest.mark.asyncio
async def test_answer_directly_tool() -> None:
    result = await execute_tool(
        "answer_directly",
        {"reason": "greeting"},
        ToolContext(user=MagicMock(), rag_service=AsyncMock()),
    )
    assert "Direct answer approved" in result.content


@pytest.mark.asyncio
async def test_unknown_tool() -> None:
    result = await execute_tool("nope", {}, ToolContext(user=MagicMock(), rag_service=AsyncMock()))
    assert "Unknown tool" in result.content


@pytest.mark.asyncio
async def test_retrieve_empty_returns_no_citations() -> None:
    rag = AsyncMock()
    rag.settings = Settings(openai_api_key="test")
    rag.retrieve.return_value = RetrievalResult(
        chunks=[],
        trace=_empty_trace("mars colony protocol"),
    )
    result = await execute_tool(
        "retrieve_documents",
        {"query": "mars colony protocol"},
        ToolContext(user=MagicMock(), rag_service=rag),
    )
    assert "Do not invent document content" in result.content
    assert result.citations == []


@pytest.mark.asyncio
async def test_retrieve_includes_page_number() -> None:
    chunk = MagicMock()
    chunk.id = "chunk-1"
    chunk.chunk_index = 0
    chunk.page_number = 3
    chunk.content = "Refund within 30 days."
    document = MagicMock()
    document.id = "doc-1"
    document.filename = "policy.pdf"
    item = MagicMock(chunk=chunk, document=document, score=0.91)
    rag = AsyncMock()
    rag.settings = Settings(openai_api_key="test")
    rag.retrieve.return_value = RetrievalResult(
        chunks=[item],
        trace=RetrievalTrace(
            attempts=[
                RetrievalAttempt(
                    query="refund",
                    grade="sufficient",
                    chunk_count=1,
                    top_k=5,
                    top_k_base=5,
                    top_k_max=8,
                    ideal_top_k=5,
                    budget_capped=False,
                    candidate_count=1,
                    rerank="disabled",
                )
            ],
            final_query="refund",
            top_k=5,
        ),
    )
    result = await execute_tool(
        "retrieve_documents",
        {"query": "refund"},
        ToolContext(user=MagicMock(), rag_service=rag),
    )
    assert "page 3" in result.content
    assert result.citations[0].page_number == 3


@pytest.mark.asyncio
async def test_retrieve_rewrites_uuid_filename_in_citations() -> None:
    chunk = MagicMock()
    chunk.id = "chunk-1"
    chunk.chunk_index = 0
    chunk.page_number = 1
    chunk.content = "Refund within 30 days."
    document = MagicMock()
    document.id = "doc-1"
    document.filename = "a3f2c1b0-1234-5678-9abc-def012345678.pdf"
    item = MagicMock(chunk=chunk, document=document, score=0.91)
    rag = AsyncMock()
    rag.settings = Settings(openai_api_key="test")
    rag.retrieve.return_value = RetrievalResult(
        chunks=[item],
        trace=RetrievalTrace(
            attempts=[
                RetrievalAttempt(
                    query="refund",
                    grade="sufficient",
                    chunk_count=1,
                    top_k=5,
                    top_k_max=8,
                    ideal_top_k=5,
                    budget_capped=False,
                )
            ],
            final_query="refund",
            top_k=5,
        ),
    )
    result = await execute_tool(
        "retrieve_documents",
        {"query": "refund"},
        ToolContext(user=MagicMock(), rag_service=rag),
    )
    assert result.citations[0].document_name == "Uploaded PDF"
    assert "Uploaded PDF" in result.content


@pytest.mark.asyncio
async def test_retrieve_skips_duplicate_effective_survey_query() -> None:
    chunk = MagicMock()
    chunk.id = "chunk-1"
    chunk.chunk_index = 0
    chunk.page_number = None
    chunk.content = "Caso 1 text"
    document = MagicMock()
    document.id = "doc-1"
    document.filename = "casos.pdf"
    item = MagicMock(chunk=chunk, document=document, score=0.8)
    rag = AsyncMock()
    rag.settings = Settings(openai_api_key="test")
    rag.retrieve.return_value = RetrievalResult(
        chunks=[item],
        trace=RetrievalTrace(
            attempts=[
                RetrievalAttempt(
                    query="resume todos los casos",
                    grade="partial",
                    chunk_count=1,
                    top_k=8,
                    top_k_max=8,
                    ideal_top_k=20,
                    budget_capped=True,
                )
            ],
            final_query="resume todos los casos",
            top_k=8,
        ),
    )
    context = ToolContext(
        user=MagicMock(),
        rag_service=rag,
        user_question="resume todos los casos del documento",
    )
    first = await execute_tool(
        "retrieve_documents",
        {"query": "Caso 1"},
        context,
    )
    second = await execute_tool(
        "retrieve_documents",
        {"query": "Caso 2"},
        context,
    )
    assert first.citations
    assert "Already retrieved" in second.content
    assert rag.retrieve.await_count == 1


@pytest.mark.asyncio
async def test_web_search_requires_query() -> None:
    result = await execute_tool(
        "web_search",
        {},
        ToolContext(user=MagicMock(), rag_service=AsyncMock(), tavily_api_key="k"),
    )
    assert "non-empty query" in result.content


@pytest.mark.asyncio
@patch("app.services.tools.registry.web_search", new_callable=AsyncMock)
async def test_web_search_success(mock_web_search) -> None:
    mock_web_search.return_value = {
        "results": [
            {
                "title": "Paris Weather",
                "url": "https://example.com/weather",
                "content": "18 C and cloudy",
                "score": 0.8,
            }
        ]
    }
    result = await execute_tool(
        "web_search",
        {"query": "paris weather"},
        ToolContext(user=MagicMock(), rag_service=AsyncMock(), tavily_api_key="k"),
    )
    assert "Paris Weather" in result.content
    assert len(result.citations) == 1
    assert result.citations[0].source_type == "web"


@pytest.mark.asyncio
@patch("app.services.tools.registry.web_search", new_callable=AsyncMock)
async def test_web_search_error(mock_web_search) -> None:
    mock_web_search.return_value = {"error": "timeout", "results": []}
    result = await execute_tool(
        "web_search",
        {"query": "q"},
        ToolContext(user=MagicMock(), rag_service=AsyncMock(), tavily_api_key="k"),
    )
    assert "failed" in result.content.lower()
