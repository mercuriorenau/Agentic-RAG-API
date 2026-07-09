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


@pytest.mark.asyncio
@patch("app.services.embedding_service.AsyncOpenAI")
async def test_upload_list_and_delete_document(mock_openai_cls, client: AsyncClient) -> None:
    mock_client = AsyncMock()
    mock_openai_cls.return_value = mock_client
    mock_client.embeddings.create.return_value = AsyncMock(data=[AsyncMock(embedding=[0.1] * 1536)])

    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    files = {
        "file": ("policy.txt", b"Our refund policy allows returns within 30 days.", "text/plain")
    }
    upload_response = await client.post("/api/v1/documents", headers=headers, files=files)
    assert upload_response.status_code == 201
    document = upload_response.json()
    assert document["status"] == "ready"
    document_id = document["id"]

    list_response = await client.get("/api/v1/documents", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["documents"]) == 1

    delete_response = await client.delete(f"/api/v1/documents/{document_id}", headers=headers)
    assert delete_response.status_code == 204

    list_after_delete = await client.get("/api/v1/documents", headers=headers)
    assert list_after_delete.json()["documents"] == []


@pytest.mark.asyncio
async def test_upload_unsupported_file_type(client: AsyncClient) -> None:
    token = await _register_and_login(client, email="badfile@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("data.csv", b"a,b,c", "text/csv")}
    response = await client.post("/api/v1/documents", headers=headers, files=files)
    assert response.status_code == 400
