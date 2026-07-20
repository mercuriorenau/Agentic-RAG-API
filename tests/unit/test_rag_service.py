from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService, RetrievedChunk, reciprocal_rank_fusion


def test_reciprocal_rank_fusion_prefers_consensus() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    scores = reciprocal_rank_fusion([[a, b, c], [b, a, c]])
    assert scores[b] > scores[c]
    assert scores[a] > scores[c]


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
async def test_retrieve_fuses_dense_and_lexical() -> None:
    db = AsyncMock()
    chunk_a = MagicMock(id=uuid4(), chunk_index=0, content="Refund within 30 days.")
    chunk_b = MagicMock(id=uuid4(), chunk_index=1, content="SKU-ALPHA-77 keyboard")
    document = MagicMock(id=uuid4(), filename="policy.txt")

    dense_result = MagicMock(all=MagicMock(return_value=[(chunk_a, document, 0.1)]))
    lexical_result = MagicMock(all=MagicMock(return_value=[(chunk_b, document, 0.4)]))
    db.execute = AsyncMock(side_effect=[dense_result, lexical_result])

    settings = MagicMock(
        top_k=5,
        candidate_multiplier=4,
        retrieval_min_score=0.2,
    )
    service = RAGService(db, settings=settings)
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536

    retrieved = await service.retrieve(MagicMock(), "refund SKU-ALPHA-77")
    assert len(retrieved) == 2
    assert {item.chunk.id for item in retrieved} == {chunk_a.id, chunk_b.id}


@pytest.mark.asyncio
async def test_retrieve_filters_below_min_score() -> None:
    db = AsyncMock()
    chunk = MagicMock(id=uuid4(), chunk_index=0, content="unrelated")
    document = MagicMock(id=uuid4(), filename="policy.txt")
    dense_result = MagicMock(all=MagicMock(return_value=[(chunk, document, 0.9)]))
    lexical_result = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(side_effect=[dense_result, lexical_result])

    settings = MagicMock(
        top_k=5,
        candidate_multiplier=4,
        retrieval_min_score=0.5,
    )
    service = RAGService(db, settings=settings)
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536

    # dense score = 1 - 0.9 = 0.1, below threshold
    assert await service.retrieve(MagicMock(), "hello") == []


@pytest.mark.asyncio
async def test_retrieve_empty() -> None:
    db = AsyncMock()
    empty = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(side_effect=[empty, empty])
    settings = MagicMock(top_k=5, candidate_multiplier=4, retrieval_min_score=0.25)
    service = RAGService(db, settings=settings)
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536
    assert await service.retrieve(MagicMock(), "hello") == []


def test_retrieved_chunk_dataclass() -> None:
    item = RetrievedChunk(chunk=MagicMock(), document=MagicMock(), score=0.9)
    assert item.score == 0.9
