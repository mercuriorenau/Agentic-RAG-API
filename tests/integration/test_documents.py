from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str = "docuser@example.com") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    return login.json()["access_token"]


async def _create_chat(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post("/api/v1/chats", headers=headers, json={"title": "Test chat"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
@patch("app.services.embedding_service.AsyncOpenAI")
async def test_upload_list_and_delete_document(mock_openai_cls, client: AsyncClient) -> None:
    mock_client = AsyncMock()
    mock_openai_cls.return_value = mock_client
    mock_client.embeddings.create.return_value = AsyncMock(data=[AsyncMock(embedding=[0.1] * 1536)])

    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = await _create_chat(client, headers)

    files = {
        "file": ("policy.txt", b"Our refund policy allows returns within 30 days.", "text/plain")
    }
    data = {"chat_id": chat_id}
    upload_response = await client.post(
        "/api/v1/documents", headers=headers, files=files, data=data
    )
    assert upload_response.status_code == 201
    document = upload_response.json()
    assert document["status"] == "ready"
    assert document["chat_id"] == chat_id
    document_id = document["id"]

    list_response = await client.get(
        "/api/v1/documents", headers=headers, params={"chat_id": chat_id}
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["documents"]) == 1

    delete_response = await client.delete(f"/api/v1/documents/{document_id}", headers=headers)
    assert delete_response.status_code == 204

    list_after_delete = await client.get(
        "/api/v1/documents", headers=headers, params={"chat_id": chat_id}
    )
    assert list_after_delete.json()["documents"] == []


@pytest.mark.asyncio
@patch("app.services.embedding_service.AsyncOpenAI")
async def test_preview_document_file(mock_openai_cls, client: AsyncClient) -> None:
    mock_client = AsyncMock()
    mock_openai_cls.return_value = mock_client
    mock_client.embeddings.create.return_value = AsyncMock(data=[AsyncMock(embedding=[0.1] * 1536)])

    token = await _register_and_login(client, email="preview@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = await _create_chat(client, headers)
    content = b"Preview this resume text for Santiago."
    upload = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("resume.txt", content, "text/plain")},
        data={"chat_id": chat_id},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    preview = await client.get(f"/api/v1/documents/{document_id}/file", headers=headers)
    assert preview.status_code == 200
    assert preview.content == content
    assert "text/plain" in preview.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_upload_unsupported_file_type(client: AsyncClient) -> None:
    token = await _register_and_login(client, email="badfile@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = await _create_chat(client, headers)
    files = {"file": ("data.csv", b"a,b,c", "text/csv")}
    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        files=files,
        data={"chat_id": chat_id},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@patch("app.services.embedding_service.AsyncOpenAI")
async def test_documents_are_isolated_per_chat(mock_openai_cls, client: AsyncClient) -> None:
    mock_client = AsyncMock()
    mock_openai_cls.return_value = mock_client
    mock_client.embeddings.create.return_value = AsyncMock(data=[AsyncMock(embedding=[0.1] * 1536)])

    token = await _register_and_login(client, email="isolation@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    chat_a = await _create_chat(client, headers)
    chat_b = (
        await client.post("/api/v1/chats", headers=headers, json={"title": "Other"})
    ).json()["id"]

    await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("a.txt", b"Document A only", "text/plain")},
        data={"chat_id": chat_a},
    )
    list_b = await client.get("/api/v1/documents", headers=headers, params={"chat_id": chat_b})
    assert list_b.json()["documents"] == []
