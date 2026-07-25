import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Document, User
from app.services.document_service import DocumentService
from app.utils.extractors import UnsupportedFileTypeError


@pytest.mark.asyncio
async def test_upload_and_ingest_txt(tmp_path) -> None:
    db = AsyncMock()
    settings = MagicMock()
    settings.upload_dir = str(tmp_path / "uploads")
    settings.chunk_size = 800
    settings.chunk_overlap = 100

    embedding_service = AsyncMock()
    embedding_service.embed_texts.return_value = [[0.1] * 1536]

    service = DocumentService(db, settings=settings, embedding_service=embedding_service)
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x")
    chat_id = uuid.uuid4()
    chat = MagicMock(id=chat_id, user_id=user.id, title="New chat")
    service._get_owned_chat = AsyncMock(return_value=chat)

    document = await service.upload_and_ingest(
        user,
        chat_id,
        "notes.txt",
        "text/plain",
        b"Our refund policy allows returns within 30 days.",
    )

    assert document.status == "ready"
    assert document.chat_id == chat_id
    assert chat.title == "notes"
    assert db.add.call_count >= 2
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_upload_renames_new_chat_from_pdf_stem(tmp_path) -> None:
    db = AsyncMock()
    settings = MagicMock()
    settings.upload_dir = str(tmp_path / "uploads")
    settings.chunk_size = 800
    settings.chunk_overlap = 100

    embedding_service = AsyncMock()
    embedding_service.embed_texts.return_value = [[0.1] * 1536]

    service = DocumentService(db, settings=settings, embedding_service=embedding_service)
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x")
    chat_id = uuid.uuid4()
    chat = MagicMock(id=chat_id, user_id=user.id, title="New chat")
    service._get_owned_chat = AsyncMock(return_value=chat)

    # Bypass PDF parsing; we only assert the chat title uses the filename stem.
    with patch("app.services.document_service.extract_pages", return_value=[(1, "lease text")]), patch(
        "app.services.document_service.chunk_pages",
        return_value=[MagicMock(page_number=1, content="lease text")],
    ):
        document = await service.upload_and_ingest(
            user,
            chat_id,
            "New Mexico Lease Agreement.pdf",
            "application/pdf",
            b"%PDF fake",
        )

    assert document.status == "ready"
    assert chat.title == "New Mexico Lease Agreement"


@pytest.mark.asyncio
async def test_upload_keeps_custom_chat_title(tmp_path) -> None:
    db = AsyncMock()
    settings = MagicMock()
    settings.upload_dir = str(tmp_path / "uploads")
    settings.chunk_size = 800
    settings.chunk_overlap = 100

    embedding_service = AsyncMock()
    embedding_service.embed_texts.return_value = [[0.1] * 1536]

    service = DocumentService(db, settings=settings, embedding_service=embedding_service)
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x")
    chat_id = uuid.uuid4()
    chat = MagicMock(id=chat_id, user_id=user.id, title="My lease chat")
    service._get_owned_chat = AsyncMock(return_value=chat)

    await service.upload_and_ingest(
        user,
        chat_id,
        "New Mexico Lease Agreement.txt",
        "text/plain",
        b"Our lease allows pets.",
    )

    assert chat.title == "My lease chat"


@pytest.mark.asyncio
async def test_upload_unsupported_type(tmp_path) -> None:
    db = AsyncMock()
    settings = MagicMock()
    settings.upload_dir = str(tmp_path / "uploads")

    service = DocumentService(db, settings=settings, embedding_service=AsyncMock())
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x")
    chat_id = uuid.uuid4()
    service._get_owned_chat = AsyncMock(return_value=MagicMock(id=chat_id, user_id=user.id))

    with pytest.raises(UnsupportedFileTypeError):
        await service.upload_and_ingest(user, chat_id, "data.csv", "text/csv", b"a,b")


@pytest.mark.asyncio
async def test_delete_document_removes_file(tmp_path) -> None:
    db = AsyncMock()
    settings = MagicMock()
    settings.upload_dir = str(tmp_path / "uploads")

    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x")
    chat_id = uuid.uuid4()
    file_path = tmp_path / "uploads" / str(user.id) / "doc.txt"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("content", encoding="utf-8")

    document = Document(
        id=uuid.uuid4(),
        user_id=user.id,
        chat_id=chat_id,
        filename="doc.txt",
        content_type="text/plain",
        file_path=str(file_path),
        status="ready",
    )

    service = DocumentService(db, settings=settings, embedding_service=AsyncMock())
    service.get_document = AsyncMock(return_value=document)

    deleted = await service.delete_document(user, document.id)
    assert deleted is True
    assert not file_path.exists()
    db.delete.assert_called_once_with(document)
