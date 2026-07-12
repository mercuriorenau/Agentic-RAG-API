from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.llm.base import ChatMessage, ToolSpec
from app.services.llm.factory import get_llm_provider
from app.services.llm.openai_provider import OpenAIProvider


def test_factory_openai() -> None:
    settings = Settings(llm_provider="openai", openai_api_key="k")
    provider = get_llm_provider(settings)
    assert isinstance(provider, OpenAIProvider)


def test_factory_anthropic() -> None:
    from app.services.llm.anthropic_provider import AnthropicProvider

    settings = Settings(llm_provider="anthropic", anthropic_api_key="k")
    provider = get_llm_provider(settings)
    assert isinstance(provider, AnthropicProvider)


def test_factory_unsupported() -> None:
    settings = Settings(llm_provider="unknown")
    with pytest.raises(ValueError, match="Unsupported"):
        get_llm_provider(settings)


@pytest.mark.asyncio
async def test_openai_provider_parses_tool_calls() -> None:
    provider = OpenAIProvider(Settings(openai_api_key="k", chat_model="gpt-4o-mini"))
    provider.client = AsyncMock()
    tool_call = MagicMock()
    tool_call.id = "call-1"
    tool_call.function.name = "retrieve_documents"
    tool_call.function.arguments = '{"query":"refund"}'
    provider.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=None, tool_calls=[tool_call]))]
    )

    result = await provider.chat_with_tools(
        [ChatMessage(role="user", content="refund?")],
        [
            ToolSpec(
                name="retrieve_documents",
                description="retrieve",
                parameters={"type": "object", "properties": {}},
            )
        ],
    )
    assert result.tool_calls[0].name == "retrieve_documents"
    assert result.tool_calls[0].arguments["query"] == "refund"


@pytest.mark.asyncio
async def test_anthropic_provider_parses_tool_use() -> None:
    from app.services.llm.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider(
        Settings(anthropic_api_key="k", anthropic_chat_model="claude-sonnet-4-20250514")
    )
    provider.client = AsyncMock()
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Looking up docs"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tu1"
    tool_block.name = "web_search"
    tool_block.input = {"query": "x"}
    provider.client.messages.create.return_value = MagicMock(content=[text_block, tool_block])

    result = await provider.chat_with_tools(
        [
            ChatMessage(role="system", content="sys"),
            ChatMessage(role="user", content="q"),
        ],
        [
            ToolSpec(
                name="web_search",
                description="web",
                parameters={"type": "object", "properties": {}},
            )
        ],
    )
    assert result.content == "Looking up docs"
    assert result.tool_calls[0].name == "web_search"


@pytest.mark.asyncio
async def test_openai_provider_invalid_json_arguments() -> None:
    provider = OpenAIProvider(Settings(openai_api_key="k"))
    provider.client = AsyncMock()
    tool_call = MagicMock()
    tool_call.id = "call-1"
    tool_call.function.name = "answer_directly"
    tool_call.function.arguments = "not-json"
    provider.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="ok", tool_calls=[tool_call]))]
    )
    result = await provider.chat_with_tools([ChatMessage(role="user", content="hi")], [])
    assert result.tool_calls[0].arguments == {}


@pytest.mark.asyncio
@patch("app.services.tools.web_search.httpx.AsyncClient")
async def test_web_search_http(mock_client_cls) -> None:
    from app.services.tools.web_search import web_search

    client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = client
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "results": [{"title": "T", "url": "https://ex.com", "content": "C", "score": 0.9}]
    }
    client.post.return_value = response

    data = await web_search("q", api_key="tvly-key")
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "T"


@pytest.mark.asyncio
async def test_web_search_unavailable_without_key() -> None:
    from app.services.tools.web_search import web_search

    data = await web_search("q", api_key="")
    assert data["unavailable"] is True
