from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import Chunk, Document, User
from app.services.embedding_service import EmbeddingService


@dataclass
class RetrievedChunk:
    chunk: Chunk
    document: Document
    score: float


class RAGService:
    """Document retrieval over pgvector. Generation is handled by AgentService."""

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(self.settings)

    async def retrieve(self, user: User, question: str) -> list[RetrievedChunk]:
        query_embedding = await self.embedding_service.embed_query(question)
        return await self._retrieve_chunks(user, query_embedding)

    async def _retrieve_chunks(
        self, user: User, query_embedding: list[float]
    ) -> list[RetrievedChunk]:
        distance = Chunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Chunk, Document, distance.label("distance"))
            .join(Document, Chunk.document_id == Document.id)
            .where(
                Document.user_id == user.id,
                Document.status == "ready",
                Chunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(self.settings.top_k)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        retrieved: list[RetrievedChunk] = []
        for chunk, document, dist in rows:
            score = 1.0 - float(dist)
            retrieved.append(RetrievedChunk(chunk=chunk, document=document, score=score))
        return retrieved
