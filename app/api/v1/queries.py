from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import User
from app.schemas.query import QueryRequest, QueryResponse
from app.services.agent_service import AgentService
from app.services.rag_service import RAGService

router = APIRouter(prefix="/queries", tags=["queries"])


async def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(RAGService(db))


@router.post("", response_model=QueryResponse)
@limiter.limit(get_settings().rate_limit_query)
async def ask_question(
    request: Request,
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
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
    return await agent_service.answer_question(
        current_user,
        body.question,
        model_mode=body.model_mode,
        model_name=body.model_name,
        history=body.history,
    )
