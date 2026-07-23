import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
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


def _validate_question_length(question: str) -> None:
    settings = get_settings()
    if len(question) > settings.max_query_length:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Question exceeds the {settings.max_query_length} character limit. "
                "This public demo limit is intentional to control API token costs."
            ),
        )


def _parse_chat_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid chat_id",
        ) from exc


def _provider_http_error(exc: Exception) -> HTTPException | None:
    name = type(exc).__name__
    message = str(exc)
    if "NotFoundError" in name or "model:" in message.lower() or "not_found_error" in message:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The selected LLM model was rejected by the provider. "
                "Try OpenAI from the model dropdown, or set ANTHROPIC_CHAT_MODEL "
                "to a current Claude ID (for example claude-sonnet-4-5)."
            ),
        )
    if "AuthenticationError" in name or "Unauthorized" in message:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider authentication failed. Check your API keys.",
        )
    return None


@router.post("", response_model=QueryResponse)
@limiter.limit(get_settings().rate_limit_query)
async def ask_question(
    request: Request,
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
    chat_service: ChatService = Depends(get_chat_service),
) -> QueryResponse:
    _validate_question_length(body.question)
    chat_id = _parse_chat_id(body.chat_id)

    chat = await chat_service.get_chat(current_user, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    history = body.history
    if not history:
        messages = await chat_service.list_messages(current_user, chat_id)
        history = _history_from_messages(messages or [])

    try:
        response = await agent_service.answer_question(
            current_user,
            body.question,
            chat_id=chat_id,
            model_mode=body.model_mode,
            model_name=body.model_name,
            history=history,
        )
    except Exception as exc:
        mapped = _provider_http_error(exc)
        if mapped:
            raise mapped from exc
        raise

    await chat_service.append_turn(current_user, chat_id, body.question, response)
    return response


@router.post("/stream")
@limiter.limit(get_settings().rate_limit_query)
async def ask_question_stream(
    request: Request,
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """SSE stream of live agent steps, ending with the final QueryResponse."""
    _validate_question_length(body.question)
    chat_id = _parse_chat_id(body.chat_id)

    chat = await chat_service.get_chat(current_user, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    history = body.history
    if not history:
        messages = await chat_service.list_messages(current_user, chat_id)
        history = _history_from_messages(messages or [])

    async def event_gen():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def on_progress(title: str, detail: str = "") -> None:
            await queue.put({"type": "step", "title": title, "detail": detail})

        async def run_agent() -> None:
            try:
                response = await agent_service.answer_question(
                    current_user,
                    body.question,
                    chat_id=chat_id,
                    model_mode=body.model_mode,
                    model_name=body.model_name,
                    history=history,
                    on_progress=on_progress,
                )
                await chat_service.append_turn(
                    current_user, chat_id, body.question, response
                )
                await queue.put(
                    {
                        "type": "done",
                        "response": response.model_dump(mode="json"),
                    }
                )
            except Exception as exc:
                mapped = _provider_http_error(exc)
                detail = mapped.detail if mapped else str(exc) or type(exc).__name__
                await queue.put({"type": "error", "detail": detail})
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_agent())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            await task

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
