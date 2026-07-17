import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import User
from app.schemas.query import ConversationTurn, QueryRequest, QueryResponse
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.rag_service import RAGService

router = APIRouter(prefix="/queries", tags=["queries"])


async def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(RAGService(db))


async def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.post("", response_model=QueryResponse)
@limiter.limit(get_settings().rate_limit_query)
async def ask_question(
    request: Request,
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
    chat_service: ChatService = Depends(get_chat_service),
) -> QueryResponse:
    settings = get_settings()
    if len(body.question) > settings.max_query_length:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Question exceeds the {settings.max_query_length} character limit. "
                "This public demo limit is intentional to control API token costs."
            ),
        )

    try:
        chat_id = uuid.UUID(body.chat_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid chat_id",
        ) from exc

    chat = await chat_service.get_chat(current_user, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    history = body.history
    if not history:
        messages = await chat_service.list_messages(current_user, chat_id)
        history = _history_from_messages(messages or [])

    response = await agent_service.answer_question(
        current_user,
        body.question,
        chat_id=chat_id,
        model_mode=body.model_mode,
        model_name=body.model_name,
        history=history,
    )
    await chat_service.append_turn(current_user, chat_id, body.question, response)
    return response


def _history_from_messages(messages) -> list[ConversationTurn]:
    history: list[ConversationTurn] = []
    pending_question: str | None = None
    for message in messages:
        if message.role == "user":
            pending_question = message.content
        elif message.role == "assistant" and pending_question:
            history.append(
                ConversationTurn(question=pending_question, answer=message.content)
            )
            pending_question = None
    return history
