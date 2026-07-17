import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.document_service import DocumentService
from app.utils.extractors import UnsupportedFileTypeError

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_response(document) -> DocumentResponse:
    return DocumentResponse(
        id=str(document.id),
        chat_id=str(document.chat_id),
        filename=document.filename,
        content_type=document.content_type,
        status=document.status,
        created_at=document.created_at.isoformat(),
    )


async def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    chat_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    settings = get_settings()
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB",
        )
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload"

    try:
        document = await document_service.upload_and_ingest(
            current_user, chat_id, filename, content_type, file_bytes
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _to_response(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    documents = await document_service.list_documents(current_user, chat_id)
    if documents is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return DocumentListResponse(documents=[_to_response(doc) for doc in documents])


@router.get("/{document_id}/file")
async def preview_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> FileResponse:
    document = await document_service.get_document(current_user, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    path = Path(document.file_path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file is missing on disk",
        )

    return FileResponse(
        path=path,
        media_type=document.content_type or "application/octet-stream",
        filename=document.filename,
        content_disposition_type="inline",
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> None:
    deleted = await document_service.delete_document(current_user, document_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
