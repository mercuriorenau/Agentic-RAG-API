import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Chat, Message, User
from app.schemas.query import QueryResponse


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_chats(self, user: User) -> list[Chat]:
        result = await self.db.execute(
            select(Chat).where(Chat.user_id == user.id).order_by(Chat.updated_at.desc())
        )
        return list(result.scalars().all())

    async def create_chat(self, user: User, title: str = "New chat") -> Chat:
        chat = Chat(id=uuid.uuid4(), user_id=user.id, title=title.strip()[:200] or "New chat")
        self.db.add(chat)
        await self.db.flush()
        return chat

    async def get_chat(self, user: User, chat_id: uuid.UUID) -> Chat | None:
        result = await self.db.execute(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id)
        )
        return result.scalar_one_or_none()

    async def rename_chat(self, user: User, chat_id: uuid.UUID, title: str) -> Chat | None:
        chat = await self.get_chat(user, chat_id)
        if chat is None:
            return None
        chat.title = title.strip()[:200] or chat.title
        await self.db.flush()
        return chat

    async def delete_chat(self, user: User, chat_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(Chat)
            .where(Chat.id == chat_id, Chat.user_id == user.id)
            .options(selectinload(Chat.documents))
        )
        chat = result.scalar_one_or_none()
        if chat is None:
            return False

        for document in chat.documents:
            path = Path(document.file_path)
            if path.is_file():
                path.unlink()

        await self.db.delete(chat)
        await self.db.flush()
        return True

    async def list_messages(self, user: User, chat_id: uuid.UUID) -> list[Message] | None:
        chat = await self.get_chat(user, chat_id)
        if chat is None:
            return None
        result = await self.db.execute(
            select(Message).where(Message.chat_id == chat.id).order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def clear_messages(self, user: User, chat_id: uuid.UUID) -> bool:
        chat = await self.get_chat(user, chat_id)
        if chat is None:
            return False
        messages = await self.list_messages(user, chat_id)
        assert messages is not None
        for message in messages:
            await self.db.delete(message)
        await self.db.flush()
        return True

    async def append_turn(
        self,
        user: User,
        chat_id: uuid.UUID,
        question: str,
        response: QueryResponse,
    ) -> Chat | None:
        chat = await self.get_chat(user, chat_id)
        if chat is None:
            return None

        self.db.add(
            Message(
                id=uuid.uuid4(),
                chat_id=chat.id,
                role="user",
                content=question,
            )
        )
        self.db.add(
            Message(
                id=uuid.uuid4(),
                chat_id=chat.id,
                role="assistant",
                content=response.answer,
                metadata_json={
                    "citations": [citation.model_dump() for citation in response.citations],
                    "tools_used": response.tools_used,
                    "route": response.route,
                    "model_mode": response.model_mode,
                    "model_provider": response.model_provider,
                    "model_name": response.model_name,
                    "model_selection_explanation": response.model_selection_explanation,
                    "retrieval_trace": response.retrieval_trace,
                },
            )
        )
        if chat.title in {"New chat", "Default chat"} and question.strip():
            chat.title = question.strip()[:80]
        await self.db.flush()
        return chat

    async def ensure_default_chat(self, user: User) -> Chat:
        chats = await self.list_chats(user)
        if chats:
            return chats[0]
        return await self.create_chat(user, title="New chat")
