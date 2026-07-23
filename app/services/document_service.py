import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models import Chat, Chunk, Document, User
from app.services.document_names import sanitize_upload_filename
from app.services.embedding_service import EmbeddingService
from app.utils.extractors import (
    UnsupportedFileTypeError,
    chunk_pages,
    extract_pages,
)

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
}


class DocumentService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(self.settings)
        self.upload_dir = Path(self.settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def _get_owned_chat(self, user: User, chat_id: uuid.UUID) -> Chat | None:
        result = await self.db.execute(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id)
        )
        return result.scalar_one_or_none()

    async def list_documents(self, user: User, chat_id: uuid.UUID) -> list[Document] | None:
        chat = await self._get_owned_chat(user, chat_id)
        if chat is None:
            return None
        result = await self.db.execute(
            select(Document)
            .where(Document.user_id == user.id, Document.chat_id == chat_id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_document(self, user: User, document_id: uuid.UUID) -> Document | None:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user.id)
        )
        return result.scalar_one_or_none()

    async def upload_and_ingest(
        self,
        user: User,
        chat_id: uuid.UUID,
        filename: str,
        content_type: str,
        file_bytes: bytes,
    ) -> Document:
        chat = await self._get_owned_chat(user, chat_id)
        if chat is None:
            raise LookupError("Chat not found")

        filename = sanitize_upload_filename(filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS and content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileTypeError("Only PDF, TXT, and Markdown files are supported")

        document_id = uuid.uuid4()
        safe_name = f"{document_id}{suffix}"
        file_path = self.upload_dir / str(user.id) / safe_name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(file_bytes)

        document = Document(
            id=document_id,
            user_id=user.id,
            chat_id=chat.id,
            filename=filename,
            content_type=content_type,
            file_path=str(file_path),
            status="processing",
        )
        self.db.add(document)
        await self.db.flush()

        try:
            pages = extract_pages(file_path, content_type)
            chunks = chunk_pages(pages, self.settings.chunk_size, self.settings.chunk_overlap)
            if not chunks:
                raise ValueError("Document contains no text after extraction")

            contents = [chunk.content for chunk in chunks]
            embeddings = await self.embedding_service.embed_texts(contents)
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                self.db.add(
                    Chunk(
                        id=uuid.uuid4(),
                        document_id=document.id,
                        chunk_index=index,
                        page_number=chunk.page_number,
                        content=chunk.content,
                        embedding=embedding,
                    )
                )

            document.status = "ready"
            logger.info(
                "document_ingested",
                document_id=str(document.id),
                user_id=str(user.id),
                chat_id=str(chat.id),
                chunk_count=len(chunks),
            )
        except Exception:
            document.status = "failed"
            logger.exception("document_ingestion_failed", document_id=str(document.id))
            raise

        await self.db.flush()
        return document

    async def delete_document(self, user: User, document_id: uuid.UUID) -> bool:
        document = await self.get_document(user, document_id)
        if document is None:
            return False

        file_path = Path(document.file_path)
        if file_path.exists():
            file_path.unlink()

        await self.db.delete(document)
        await self.db.flush()
        return True
