from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.schemas.query import ConversationTurn
from app.services.agent_service import AgentService, resolve_route
from app.services.llm.base import ChatResult, ToolCall


def test_resolve_route() -> None:
    assert resolve_route(["retrieve_documents"]) == "retrieve"
    assert resolve_route(["web_search"]) == "web"
    assert resolve_route(["answer_directly"]) == "direct"
    assert resolve_route(["retrieve_documents", "web_search"]) == "mixed"
    assert resolve_route([]) == "direct"


@pytest.mark.asyncio
async def test_agent_direct_answer_without_tools() -> None:
    llm = AsyncMock()
    llm.chat_with_tools.return_value = ChatResult(content="Hello!", tool_calls=[])
    rag = MagicMock()
    service = AgentService(rag_service=rag, llm=llm)

    response = await service.answer_question(MagicMock(id="u1"), "Hi")
    assert response.answer == "Hello!"
    assert response.route == "direct"
    assert response.tools_used == []
    assert response.citations == []
    assert response.model_mode == "auto"
    assert response.model_provider == "openai"


@pytest.mark.asyncio
async def test_agent_uses_retrieve_tool() -> None:
    llm = AsyncMock()
    llm.chat_with_tools.side_effect = [
        ChatResult(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="retrieve_documents",
                    arguments={"query": "refund"},
                )
            ],
        ),
        ChatResult(content="Refunds are allowed within 30 days.", tool_calls=[]),
    ]

    rag = AsyncMock()
    chunk = MagicMock()
    chunk.id = "c1"
    chunk.chunk_index = 0
    chunk.content = "Refunds within 30 days."
    document = MagicMock()
    document.id = "d1"
    document.filename = "policy.txt"
    retrieved = MagicMock(chunk=chunk, document=document, score=0.91)
    rag.retrieve.return_value = MagicMock(chunks=[retrieved], trace=MagicMock(to_dicts=lambda: []))

    settings = Settings(openai_api_key="openai", agent_max_tool_rounds=3)

    service = AgentService(rag_service=rag, settings=settings, llm=llm)
    response = await service.answer_question(MagicMock(id="u1"), "What is the refund policy?")

    assert "30 days" in response.answer
    assert response.route == "retrieve"
    assert response.tools_used == ["retrieve_documents"]
    assert len(response.citations) == 1
    assert response.citations[0].document_name == "policy.txt"
    assert "Auto mode inspected" in response.model_selection_explanation


@pytest.mark.asyncio
async def test_agent_web_search_without_key() -> None:
    llm = AsyncMock()
    llm.chat_with_tools.side_effect = [
        ChatResult(
            content=None,
            tool_calls=[ToolCall(id="call-1", name="web_search", arguments={"query": "paris"})],
        ),
        ChatResult(content="I do not have live weather data.", tool_calls=[]),
    ]
    settings = Settings(openai_api_key="openai", agent_max_tool_rounds=3)
    service = AgentService(rag_service=AsyncMock(), settings=settings, llm=llm)

    response = await service.answer_question(MagicMock(id="u1"), "Weather in Paris?")
    assert response.route == "web"
    assert "web_search" in response.tools_used


@pytest.mark.asyncio
async def test_agent_max_rounds_forces_final_answer() -> None:
    llm = AsyncMock()
    llm.chat_with_tools.side_effect = [
        ChatResult(
            content=None,
            tool_calls=[
                ToolCall(id="c1", name="answer_directly", arguments={"reason": "greeting"})
            ],
        ),
        ChatResult(content="Final after cap.", tool_calls=[]),
    ]
    settings = Settings(openai_api_key="openai", agent_max_tool_rounds=1)
    service = AgentService(rag_service=AsyncMock(), settings=settings, llm=llm)

    response = await service.answer_question(MagicMock(id="u1"), "Hello")
    assert response.answer == "Final after cap."
    assert response.tools_used == ["answer_directly"]


@pytest.mark.asyncio
async def test_agent_nudges_retrieve_when_chat_has_docs(monkeypatch) -> None:
    async def fake_docs(*_args, **_kwargs):
        return ["erp-cases.pdf"]

    monkeypatch.setattr(
        "app.services.agent_service._list_ready_documents",
        fake_docs,
    )

    llm = AsyncMock()
    llm.chat_with_tools.side_effect = [
        ChatResult(
            content="Could you specify which document?",
            tool_calls=[],
        ),
        ChatResult(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="retrieve_documents",
                    arguments={"query": "each case summary"},
                )
            ],
        ),
        ChatResult(content="Case summaries from the upload.", tool_calls=[]),
    ]

    rag = AsyncMock()
    chunk = MagicMock()
    chunk.id = "c1"
    chunk.chunk_index = 0
    chunk.content = "Case 1 failed migration."
    document = MagicMock()
    document.id = "d1"
    document.filename = "erp-cases.pdf"
    retrieved = MagicMock(chunk=chunk, document=document, score=0.9)
    rag.retrieve.return_value = MagicMock(
        chunks=[retrieved],
        trace=MagicMock(to_dicts=lambda: []),
    )

    settings = Settings(openai_api_key="openai", agent_max_tool_rounds=3)
    service = AgentService(rag_service=rag, settings=settings, llm=llm)
    response = await service.answer_question(
        MagicMock(id="u1"),
        "Describe shortly each case of the document",
        chat_id=MagicMock(),
    )

    assert response.route == "retrieve"
    assert "retrieve_documents" in response.tools_used
    assert "Case summaries" in response.answer
    system = llm.chat_with_tools.call_args_list[0].args[0][0].content
    assert "erp-cases.pdf" in system
    second_pass = llm.chat_with_tools.call_args_list[1].args[0]
    assert any(
        message.role == "user" and "Call retrieve_documents" in (message.content or "")
        for message in second_pass
    )


def test_looks_like_document_question() -> None:
    from app.services.agent_service import _looks_like_document_question

    assert _looks_like_document_question("Describe shortly each case of the document")
    assert not _looks_like_document_question("What is 2+2?")



@pytest.mark.asyncio
async def test_agent_honors_user_selected_anthropic_model() -> None:
    llm = AsyncMock()
    llm.chat_with_tools.return_value = ChatResult(content="Selected model answer.", tool_calls=[])
    rag = MagicMock()
    service = AgentService(rag_service=rag, llm=llm)

    response = await service.answer_question(
        MagicMock(id="u1"),
        "Explain the tradeoffs.",
        model_mode="anthropic",
        model_name="claude-sonnet-4-5",
    )

    assert response.model_mode == "anthropic"
    assert response.model_provider == "anthropic"
    assert response.model_name == "claude-sonnet-4-5"


@pytest.mark.asyncio
async def test_agent_includes_conversation_history() -> None:
    llm = AsyncMock()
    llm.chat_with_tools.return_value = ChatResult(
        content="Yes — based on the resume we just discussed, he looks hireable.",
        tool_calls=[],
    )
    service = AgentService(rag_service=MagicMock(), llm=llm)

    await service.answer_question(
        MagicMock(id="u1"),
        "do you think he is in a good position to find a job",
        history=[
            ConversationTurn(
                question="im talking about Santiago his resume is uploaded",
                answer="Santiago is a software engineering graduate with strong projects.",
            )
        ],
    )

    messages = llm.chat_with_tools.call_args.args[0]
    roles = [message.role for message in messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert "Santiago" in messages[1].content
    assert "good position" in messages[3].content
