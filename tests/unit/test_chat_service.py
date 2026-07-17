import uuid
from unittest.mock import AsyncMock

import pytest

from app.models import Chat, User
from app.schemas.query import QueryResponse
from app.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_create_chat() -> None:
    db = AsyncMock()
    service = ChatService(db)
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x")

    chat = await service.create_chat(user, title="Resume thread")
    assert chat.title == "Resume thread"
    assert chat.user_id == user.id
    db.add.assert_called_once()
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_append_turn_renames_new_chat() -> None:
    db = AsyncMock()
    service = ChatService(db)
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x")
    chat = Chat(id=uuid.uuid4(), user_id=user.id, title="New chat")
    service.get_chat = AsyncMock(return_value=chat)

    response = QueryResponse(
        answer="Santiago looks strong.",
        citations=[],
        tools_used=["retrieve_documents"],
        route="retrieve",
        model_mode="auto",
        model_provider="openai",
        model_name="gpt-4o",
        model_selection_explanation="test",
    )
    updated = await service.append_turn(
        user,
        chat.id,
        "Tell me about Santiago",
        response,
    )
    assert updated is not None
    assert updated.title == "Tell me about Santiago"
    assert db.add.call_count == 2
