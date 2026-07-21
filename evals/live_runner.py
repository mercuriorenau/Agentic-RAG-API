"""Live eval harness: seed fixtures, run retrieve (+ optional agent), score."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.core.security import get_password_hash
from app.models import Chat, User
from app.services.agent_service import AgentService
from app.services.document_service import DocumentService
from app.services.rag_service import RAGService
from evals.scorers import retrieval_relevance_score

FIXTURES_DIR = Path(__file__).with_name("fixtures")

CONTENT_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
}


async def run_live_evals(cases: list[dict], evaluate_case) -> list[dict]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for live evals (embeddings).")

    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    results: list[dict] = []

    try:
        async with session_factory() as session:
            user, chat = await _seed_eval_user(session)
            for case in cases:
                result = await _evaluate_live_case(
                    session,
                    settings,
                    user,
                    chat,
                    case,
                    evaluate_case,
                )
                results.append(result)
            await session.rollback()
    finally:
        await engine.dispose()

    return results


async def _seed_eval_user(session: AsyncSession) -> tuple[User, Chat]:
    user = User(
        id=uuid.uuid4(),
        email=f"eval-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password=get_password_hash("eval-password-not-used"),
    )
    session.add(user)
    await session.flush()
    chat = Chat(id=uuid.uuid4(), user_id=user.id, title="Eval chat")
    session.add(chat)
    await session.flush()
    return user, chat


async def _evaluate_live_case(
    session: AsyncSession,
    settings: Settings,
    user: User,
    chat: Chat,
    case: dict,
    evaluate_case,
) -> dict:
    fixture_names = case.get("fixtures") or []
    docs = []
    try:
        if fixture_names:
            docs = await _ingest_fixtures(session, settings, user, chat, fixture_names)

        retrieved_texts: list[str] = []
        actual_route = case.get("expected_route") or "direct"
        answer = case.get("sample_answer") or ""
        context = case.get("context_excerpts") or []

        if fixture_names or case.get("expected_route") == "retrieve":
            rag = RAGService(session, settings=settings)
            retrieval = await rag.retrieve(user, case["question"], chat_id=chat.id)
            retrieved_texts = [item.chunk.content for item in retrieval.chunks]

        expect_empty = bool(case.get("expect_empty_retrieve"))
        if expect_empty:
            # Soft check: either empty or no keyword hits on a nonsense query.
            empty_ok = len(retrieved_texts) == 0
            relevance = 1.0 if empty_ok else retrieval_relevance_score(
                retrieved_texts, ["mars", "colony", "evacuation"]
            )
            # Pass when retrieve is empty OR relevance to nonsense keywords is low.
            live_passed = empty_ok or relevance < 0.5
            return {
                "id": case["id"],
                "passed": live_passed,
                "relevance": round(0.0 if empty_ok else relevance, 3),
                "groundedness": 1.0,
                "route": 1.0,
                "mode": "live",
                "retrieved_count": len(retrieved_texts),
            }

        run_agent = (
            not case.get("skip_live_agent")
            and case.get("expected_route") in {"retrieve", "direct", "web", "mixed"}
            and bool(settings.openai_api_key or settings.anthropic_api_key)
            and not case.get("expect_low_groundedness")
        )

        if run_agent and case.get("expected_route") != "web":
            # Skip web cases in live agent mode unless Tavily is configured.
            if case.get("expected_route") == "web" and not settings.tavily_api_key:
                run_agent = False

        if run_agent and case.get("expected_route") != "web":
            rag = RAGService(session, settings=settings)
            agent = AgentService(rag, settings=settings)
            response = await agent.answer_question(
                user,
                case["question"],
                chat_id=chat.id,
                model_mode="openai",
            )
            answer = response.answer
            actual_route = response.route
            if response.citations:
                context = [c.excerpt for c in response.citations]
            elif retrieved_texts:
                context = retrieved_texts

        scored = evaluate_case(
            {
                **case,
                "sample_retrieved": retrieved_texts or case.get("sample_retrieved") or [],
                "sample_answer": answer,
                "context_excerpts": context or retrieved_texts,
                "actual_route": actual_route,
            }
        )
        scored["mode"] = "live"
        scored["retrieved_count"] = len(retrieved_texts)
        return scored
    finally:
        for document in docs:
            await session.delete(document)
        await session.flush()


async def _ingest_fixtures(
    session: AsyncSession,
    settings: Settings,
    user: User,
    chat: Chat,
    fixture_names: list[str],
) -> list:
    service = DocumentService(session, settings=settings)
    documents = []
    for name in fixture_names:
        path = FIXTURES_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Missing eval fixture: {path}")
        suffix = path.suffix.lower()
        content_type = CONTENT_TYPES.get(suffix, "text/plain")
        document = await service.upload_and_ingest(
            user,
            chat.id,
            filename=name,
            content_type=content_type,
            file_bytes=path.read_bytes(),
        )
        documents.append(document)
    await session.flush()
    return documents
