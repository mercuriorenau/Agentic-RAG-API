from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService, RetrievedChunk, reciprocal_rank_fusion


def _settings(**overrides):
    base = {
        "top_k": 5,
        "top_k_max": 8,
        "adaptive_top_k": True,
        "candidate_multiplier": 4,
        "retrieval_min_score": 0.2,
        "rerank_enabled": False,
        "self_rag_enabled": False,
        "self_rag_max_retries": 2,
    }
    base.update(overrides)
    return MagicMock(**base)


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

    service = RAGService(db, settings=_settings())
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536

    result = await service.retrieve(MagicMock(), "refund SKU-ALPHA-77")
    assert len(result.chunks) == 2
    assert {item.chunk.id for item in result.chunks} == {chunk_a.id, chunk_b.id}


@pytest.mark.asyncio
async def test_retrieve_filters_below_min_score() -> None:
    db = AsyncMock()
    chunk = MagicMock(id=uuid4(), chunk_index=0, content="unrelated")
    document = MagicMock(id=uuid4(), filename="policy.txt")
    dense_result = MagicMock(all=MagicMock(return_value=[(chunk, document, 0.9)]))
    lexical_result = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(side_effect=[dense_result, lexical_result])

    service = RAGService(db, settings=_settings(retrieval_min_score=0.5))
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536

    result = await service.retrieve(MagicMock(), "hello")
    assert result.chunks == []


@pytest.mark.asyncio
async def test_retrieve_empty() -> None:
    db = AsyncMock()
    empty = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(side_effect=[empty, empty])
    service = RAGService(db, settings=_settings(retrieval_min_score=0.25))
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536
    result = await service.retrieve(MagicMock(), "hello")
    assert result.chunks == []


@pytest.mark.asyncio
async def test_retrieve_uses_reranker_order() -> None:
    db = AsyncMock()
    chunk_a = MagicMock(id=uuid4(), chunk_index=0, content="alpha")
    chunk_b = MagicMock(id=uuid4(), chunk_index=1, content="beta")
    document = MagicMock(id=uuid4(), filename="doc.txt")
    dense_result = MagicMock(
        all=MagicMock(return_value=[(chunk_a, document, 0.1), (chunk_b, document, 0.2)])
    )
    lexical_result = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(side_effect=[dense_result, lexical_result])

    reranker = AsyncMock()
    reranker.rank_indices.return_value = [1, 0]
    service = RAGService(db, settings=_settings(top_k=2, rerank_enabled=True), reranker=reranker)
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536

    result = await service.retrieve(MagicMock(), "beta first")
    assert [item.chunk.id for item in result.chunks] == [chunk_b.id, chunk_a.id]


@pytest.mark.asyncio
async def test_retrieve_fail_open_when_rerank_returns_none() -> None:
    db = AsyncMock()
    chunk = MagicMock(id=uuid4(), chunk_index=0, content="keep me")
    document = MagicMock(id=uuid4(), filename="doc.txt")
    dense_result = MagicMock(all=MagicMock(return_value=[(chunk, document, 0.1)]))
    lexical_result = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(side_effect=[dense_result, lexical_result])

    reranker = AsyncMock()
    reranker.rank_indices.return_value = None
    service = RAGService(db, settings=_settings(rerank_enabled=True), reranker=reranker)
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536

    result = await service.retrieve(MagicMock(), "keep")
    assert len(result.chunks) == 1
    assert result.chunks[0].chunk.id == chunk.id


@pytest.mark.asyncio
async def test_self_rag_retries_with_rewritten_query() -> None:
    db = AsyncMock()
    chunk = MagicMock(id=uuid4(), chunk_index=0, content="OMSCS recommendation letter")
    document = MagicMock(id=uuid4(), filename="doc.txt")
    first_dense = MagicMock(all=MagicMock(return_value=[(chunk, document, 0.2)]))
    first_lex = MagicMock(all=MagicMock(return_value=[]))
    second_dense = MagicMock(all=MagicMock(return_value=[(chunk, document, 0.05)]))
    second_lex = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(side_effect=[first_dense, first_lex, second_dense, second_lex])

    self_rag = AsyncMock()
    self_rag.grade_evidence.side_effect = ["irrelevant", "sufficient"]
    self_rag.rewrite_query.return_value = "Georgia Tech OMSCS recommendation"

    service = RAGService(
        db,
        settings=_settings(self_rag_enabled=True, self_rag_max_retries=2),
        self_rag=self_rag,
    )
    service.embedding_service = AsyncMock()
    service.embedding_service.embed_query.return_value = [1.0] * 1536

    result = await service.retrieve(MagicMock(), "what is this about?")
    assert len(result.chunks) == 1
    assert len(result.trace.attempts) == 2
    assert result.trace.attempts[0].grade == "irrelevant"
    assert result.trace.attempts[1].grade == "sufficient"
    assert result.trace.final_query == "Georgia Tech OMSCS recommendation"
    self_rag.rewrite_query.assert_awaited_once()


def test_retrieved_chunk_dataclass() -> None:
    item = RetrievedChunk(chunk=MagicMock(), document=MagicMock(), score=0.9)
    assert item.score == 0.9
