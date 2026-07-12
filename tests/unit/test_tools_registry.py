from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tools.registry import ToolContext, execute_tool


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
async def test_retrieve_requires_query() -> None:
    result = await execute_tool(
        "retrieve_documents",
        {"query": "  "},
        ToolContext(user=MagicMock(), rag_service=AsyncMock()),
    )
    assert "non-empty query" in result.content


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
