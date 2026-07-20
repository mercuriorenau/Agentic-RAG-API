import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import Chunk, Document, User
from app.services.embedding_service import EmbeddingService


@dataclass
class RetrievedChunk:
    chunk: Chunk
    document: Document
    score: float


def reciprocal_rank_fusion(
    ranked_id_lists: list[list[uuid.UUID]],
    *,
    k: int = 60,
) -> dict[uuid.UUID, float]:
    """Merge ranked lists with Reciprocal Rank Fusion."""
    scores: dict[uuid.UUID, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, chunk_id in enumerate(ranked_ids):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


class RAGService:
    """Document retrieval over pgvector + full-text search. Generation is in AgentService."""

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(self.settings)

    async def retrieve(
        self,
        user: User,
        question: str,
        *,
        chat_id: uuid.UUID | None = None,
    ) -> list[RetrievedChunk]:
        query_embedding = await self.embedding_service.embed_query(question)
        return await self._retrieve_chunks(user, question, query_embedding, chat_id=chat_id)

    async def _retrieve_chunks(
        self,
        user: User,
        question: str,
        query_embedding: list[float],
        *,
        chat_id: uuid.UUID | None = None,
    ) -> list[RetrievedChunk]:
        candidate_limit = max(
            self.settings.top_k * self.settings.candidate_multiplier,
            self.settings.top_k,
        )

        dense_rows = await self._dense_retrieve(
            user, query_embedding, chat_id=chat_id, limit=candidate_limit
        )
        lexical_rows = await self._lexical_retrieve(
            user, question, chat_id=chat_id, limit=candidate_limit
        )

        by_id: dict[uuid.UUID, tuple[Chunk, Document, float | None, float | None]] = {}
        dense_ids: list[uuid.UUID] = []
        for chunk, document, dense_score in dense_rows:
            dense_ids.append(chunk.id)
            by_id[chunk.id] = (chunk, document, dense_score, None)

        lexical_ids: list[uuid.UUID] = []
        for chunk, document, lexical_score in lexical_rows:
            lexical_ids.append(chunk.id)
            existing = by_id.get(chunk.id)
            if existing:
                by_id[chunk.id] = (existing[0], existing[1], existing[2], lexical_score)
            else:
                by_id[chunk.id] = (chunk, document, None, lexical_score)

        if not by_id:
            return []

        rrf_scores = reciprocal_rank_fusion([dense_ids, lexical_ids])
        fused: list[RetrievedChunk] = []
        for chunk_id, rrf_score in sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True):
            chunk, document, dense_score, lexical_score = by_id[chunk_id]
            display_score = dense_score if dense_score is not None else (lexical_score or rrf_score)
            fused.append(RetrievedChunk(chunk=chunk, document=document, score=float(display_score)))

        filtered = [
            item
            for item in fused
            if item.score >= self.settings.retrieval_min_score
        ]
        if not filtered:
            return []

        return filtered[: self.settings.top_k]

    async def _dense_retrieve(
        self,
        user: User,
        query_embedding: list[float],
        *,
        chat_id: uuid.UUID | None,
        limit: int,
    ) -> list[tuple[Chunk, Document, float]]:
        distance = Chunk.embedding.cosine_distance(query_embedding)
        stmt = self._base_chunk_query(user, chat_id=chat_id).where(Chunk.embedding.is_not(None))
        stmt = stmt.add_columns(distance.label("distance")).order_by(distance).limit(limit)
        result = await self.db.execute(stmt)
        rows = result.all()
        return [(chunk, document, 1.0 - float(dist)) for chunk, document, dist in rows]

    async def _lexical_retrieve(
        self,
        user: User,
        question: str,
        *,
        chat_id: uuid.UUID | None,
        limit: int,
    ) -> list[tuple[Chunk, Document, float]]:
        query = question.strip()
        if not query:
            return []

        ts_vector = func.to_tsvector("english", Chunk.content)
        ts_query = func.plainto_tsquery("english", query)
        rank = func.ts_rank_cd(ts_vector, ts_query)
        stmt = (
            self._base_chunk_query(user, chat_id=chat_id)
            .where(ts_vector.op("@@")(ts_query))
            .add_columns(rank.label("rank"))
            .order_by(rank.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        scored: list[tuple[Chunk, Document, float]] = []
        for chunk, document, rank_value in rows:
            # ts_rank_cd is typically small; map into a 0-1-ish band for thresholding.
            score = min(1.0, float(rank_value) * 2.0) if rank_value is not None else 0.0
            scored.append((chunk, document, score))
        return scored

    def _base_chunk_query(
        self,
        user: User,
        *,
        chat_id: uuid.UUID | None,
    ) -> Select:
        filters = [
            Document.user_id == user.id,
            Document.status == "ready",
        ]
        if chat_id is not None:
            filters.append(Document.chat_id == chat_id)
        return (
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(*filters)
        )
