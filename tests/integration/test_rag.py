from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.llm.base import ChatResult, ToolCall


def _embedding(vector: list[float]):
    return AsyncMock(data=[AsyncMock(embedding=vector)])


async def _auth_and_chat(client: AsyncClient, email: str) -> tuple[dict[str, str], str]:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    chat = await client.post("/api/v1/chats", headers=headers, json={"title": "RAG chat"})
    return headers, chat.json()["id"]


@pytest.mark.asyncio
@patch("app.services.embedding_service.AsyncOpenAI")
@patch("app.services.agent_service.get_llm_provider")
async def test_rag_query_returns_answer_and_citations(
    mock_get_llm, mock_embed_cls, client: AsyncClient
) -> None:
    vector = [1.0] + [0.0] * 1535
    embed_client = AsyncMock()
    mock_embed_cls.return_value = embed_client
    embed_client.embeddings.create.side_effect = lambda **kwargs: _embedding(vector)

    llm = AsyncMock()
    mock_get_llm.return_value = llm
    llm.chat_with_tools.side_effect = [
        ChatResult(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="retrieve_documents",
                    arguments={"query": "refund policy"},
                )
            ],
        ),
        ChatResult(
            content="Returns are allowed within 30 days.",
            tool_calls=[],
        ),
    ]

    headers, chat_id = await _auth_and_chat(client, "raguser@example.com")

    files = {
        "file": ("policy.txt", b"Our refund policy allows returns within 30 days.", "text/plain")
    }
    upload = await client.post(
        "/api/v1/documents",
        headers=headers,
        files=files,
        data={"chat_id": chat_id},
    )
    assert upload.status_code == 201

    query_response = await client.post(
        "/api/v1/queries",
        headers=headers,
        json={
            "question": "What is the refund policy?",
            "chat_id": chat_id,
            "model_mode": "auto",
        },
    )
    assert query_response.status_code == 200
    body = query_response.json()
    assert "30 days" in body["answer"]
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["document_name"] == "policy.txt"
    assert body["route"] == "retrieve"
    assert "retrieve_documents" in body["tools_used"]
    assert body["model_mode"] == "auto"
    assert body["model_provider"] in {"openai", "anthropic"}
    assert body["model_name"]
    assert "Auto mode inspected" in body["model_selection_explanation"]

    messages = await client.get(f"/api/v1/chats/{chat_id}/messages", headers=headers)
    assert messages.status_code == 200
    assert len(messages.json()["messages"]) == 2


@pytest.mark.asyncio
async def test_query_rejects_oversized_question(client: AsyncClient) -> None:
    headers, chat_id = await _auth_and_chat(client, "limituser@example.com")

    response = await client.post(
        "/api/v1/queries",
        headers=headers,
        json={"question": "x" * 601, "chat_id": chat_id},
    )

    assert response.status_code == 413
    assert "token costs" in response.json()["detail"]
