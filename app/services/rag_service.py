import uuid
from dataclasses import dataclass, field

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import Chunk, Document, User
from app.services.embedding_service import EmbeddingService
from app.services.rerank_service import LLMReranker
from app.services.retrieval_budget import resolve_top_k
from app.services.self_rag import SelfRAGHelper, needs_retry


@dataclass
class RetrievedChunk:
    chunk: Chunk
    document: Document
    score: float


@dataclass
class RetrievalAttempt:
    query: str
    grade: str
    chunk_count: int
    top_k: int = 0


@dataclass
class RetrievalTrace:
    attempts: list[RetrievalAttempt] = field(default_factory=list)
    final_query: str = ""
    top_k: int = 0

    def to_dicts(self) -> list[dict]:
        return [
            {
                "query": item.query,
                "grade": item.grade,
                "chunk_count": item.chunk_count,
                "top_k": item.top_k,
            }
            for item in self.attempts
        ]


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    trace: RetrievalTrace


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
        reranker: LLMReranker | None = None,
        self_rag: SelfRAGHelper | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(self.settings)
        self.reranker = reranker or LLMReranker(self.settings)
        self.self_rag = self_rag or SelfRAGHelper(self.settings)

    async def retrieve(
        self,
        user: User,
        question: str,
        *,
        chat_id: uuid.UUID | None = None,
    ) -> RetrievalResult:
        trace = RetrievalTrace(final_query=question)
        query = question.strip()
        best_chunks: list[RetrievedChunk] = []
        top_k = resolve_top_k(query, self.settings)
        trace.top_k = top_k

        max_attempts = 1 + (
            self.settings.self_rag_max_retries if self.settings.self_rag_enabled else 0
        )

        for attempt_index in range(max_attempts):
            chunks = await self._retrieve_once(
                user, query, chat_id=chat_id, top_k=top_k
            )
            passages = [item.chunk.content for item in chunks]
            if self.settings.self_rag_enabled:
                grade = await self.self_rag.grade_evidence(query, passages)
            else:
                grade = "sufficient" if chunks else "irrelevant"

            trace.attempts.append(
                RetrievalAttempt(
                    query=query,
                    grade=grade,
                    chunk_count=len(chunks),
                    top_k=top_k,
                )
            )
            trace.final_query = query

            if chunks and (not best_chunks or grade == "sufficient"):
                best_chunks = chunks
            if grade == "sufficient" and chunks:
                return RetrievalResult(chunks=chunks, trace=trace)
            if not self.settings.self_rag_enabled:
                break
            if attempt_index >= max_attempts - 1 or not needs_retry(grade):
                break

            rewritten = await self.self_rag.rewrite_query(query, passages)
            if not rewritten:
                break
            query = rewritten

        return RetrievalResult(chunks=best_chunks, trace=trace)

    async def _retrieve_once(
        self,
        user: User,
        question: str,
        *,
        chat_id: uuid.UUID | None = None,
        top_k: int,
    ) -> list[RetrievedChunk]:
        query_embedding = await self.embedding_service.embed_query(question)
        return await self._retrieve_chunks(
            user, question, query_embedding, chat_id=chat_id, top_k=top_k
        )

    async def _retrieve_chunks(
        self,
        user: User,
        question: str,
        query_embedding: list[float],
        *,
        chat_id: uuid.UUID | None = None,
        top_k: int,
    ) -> list[RetrievedChunk]:
        candidate_limit = max(
            top_k * self.settings.candidate_multiplier,
            top_k,
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
        for chunk_id, rrf_score in sorted(
            rrf_scores.items(), key=lambda item: item[1], reverse=True
        ):
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

        return await self._rerank(question, filtered, top_k=top_k)

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

    async def _rerank(
        self,
        question: str,
        candidates: list[RetrievedChunk],
        *,
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not self.settings.rerank_enabled:
            return candidates[:top_k]

        order = await self.reranker.rank_indices(
            question,
            [item.chunk.content for item in candidates],
        )
        if order is None:
            return candidates[:top_k]
        reranked = [candidates[i] for i in order if 0 <= i < len(candidates)]
        return reranked[:top_k]
