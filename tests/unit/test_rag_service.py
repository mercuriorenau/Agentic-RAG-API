from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService, RetrievedChunk


@pytest.mark.asyncio
async def test_embed_texts_returns_vectors() -> None:
    service = EmbeddingService()
    service.client = AsyncMock()
    service.client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2]), MagicMock(embedding=[0.3, 0.4])]
    )

    vectors = await service.embed_texts(["a", "b"])
    assert len(vectors) == 2
    assert vectors[0] == [0.1, 0.2]


@pytest.mark.asyncio
async def test_embed_texts_empty_list() -> None:
    service = EmbeddingService()
    assert await service.embed_texts([]) == []


@pytest.mark.asyncio
async def test_retrieve_returns_scored_chunks() -> None:
    db = AsyncMock()
    chunk = MagicMock()
    chunk.id = "chunk-id"
    chunk.chunk_index = 0
    chunk.content = "Refund within 30 days."
    document = MagicMock()
    document.id = "doc-id"
    document.filename = "policy.txt"
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[(chunk, document, 0.1)]))

    service = RAGService(db)
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536

    user = MagicMock()
    retrieved = await service.retrieve(user, "refund policy?")
    assert len(retrieved) == 1
    assert retrieved[0].document.filename == "policy.txt"
    assert retrieved[0].score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_retrieve_empty() -> None:
    db = AsyncMock()
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    service = RAGService(db)
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536
    assert await service.retrieve(MagicMock(), "hello") == []


def test_retrieved_chunk_dataclass() -> None:
    item = RetrievedChunk(chunk=MagicMock(), document=MagicMock(), score=0.9)
    assert item.score == 0.9
