import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.chat import (
    ChatCreate,
    ChatListResponse,
    ChatResponse,
    ChatUpdate,
    MessageListResponse,
    MessageResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])


def _chat_response(chat) -> ChatResponse:
    return ChatResponse(
        id=str(chat.id),
        title=chat.title,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
    )


def _message_response(message) -> MessageResponse:
    return MessageResponse(
        id=str(message.id),
        role=message.role,
        content=message.content,
        metadata=message.metadata_json,
        created_at=message.created_at.isoformat(),
    )


async def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.get("", response_model=ChatListResponse)
async def list_chats(
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatListResponse:
    chats = await chat_service.list_chats(current_user)
    if not chats:
        chats = [await chat_service.create_chat(current_user)]
    return ChatListResponse(chats=[_chat_response(chat) for chat in chats])


@router.post("", response_model=ChatResponse, status_code=201)
async def create_chat(
    body: ChatCreate,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    chat = await chat_service.create_chat(current_user, title=body.title)
    return _chat_response(chat)


@router.patch("/{chat_id}", response_model=ChatResponse)
async def rename_chat(
    chat_id: uuid.UUID,
    body: ChatUpdate,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    chat = await chat_service.rename_chat(current_user, chat_id, body.title)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return _chat_response(chat)


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    deleted = await chat_service.delete_chat(current_user, chat_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")


@router.get("/{chat_id}/messages", response_model=MessageListResponse)
async def list_messages(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageListResponse:
    messages = await chat_service.list_messages(current_user, chat_id)
    if messages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return MessageListResponse(messages=[_message_response(message) for message in messages])


@router.delete("/{chat_id}/messages", status_code=204)
async def clear_messages(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    cleared = await chat_service.clear_messages(current_user, chat_id)
    if not cleared:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
