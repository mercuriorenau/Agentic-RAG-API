import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models import Document, User
from app.schemas.query import Citation, ConversationTurn, QueryResponse
from app.services.llm.base import ChatMessage, LLMProvider
from app.services.llm.factory import get_llm_provider
from app.services.llm.model_selector import ModelSelection, select_model
from app.services.rag_service import RAGService
from app.services.tools import TOOL_SPECS, ToolContext, execute_tool

logger = get_logger(__name__)

ProgressCallback = Callable[[str, str], Awaitable[None]]

_TOOL_STEP_TITLES = {
    "retrieve_documents": "Search uploads",
    "web_search": "Web search",
    "answer_directly": "Answer directly",
}

SYSTEM_PROMPT = (
    "You are an agent that answers user questions using tools when helpful. "
    "Available tools: retrieve_documents (search uploaded files), web_search "
    "(public web), answer_directly (general knowledge with no external lookup). "
    "Choose the minimum set of tools needed. Prefer retrieve_documents for questions "
    "about the user's documents. Use web_search for current or external facts. "
    "Use answer_directly for greetings, simple definitions, or math that needs no sources. "
    "When this chat lists uploaded documents, treat phrases like 'the document', "
    "'this file', 'the PDF', 'each case', or 'the upload' as referring to those files — "
    "call retrieve_documents before answering. Do not ask which document if only one "
    "ready file is listed. Do not answer document-content questions with no tool call. "
    "For survey questions that ask about many cases/sections, prefer one "
    "retrieve_documents call using the user's wording or document-language keywords. "
    "At most one follow-up retrieve if the first return is empty or irrelevant — "
    "do not fan out many similar searches. "
    "After tool results arrive, produce a final answer. "
    "CRITICAL language rule: write the ENTIRE final answer in the language of the "
    "user's latest question only — including coverage caveats and follow-up offers. "
    "Do not follow the document language, citation language, or prior-turn language "
    "when choosing reply language. Example: English question → English answer even if "
    "the PDF and earlier chat turns are Spanish. "
    "When document or web context is provided, ground every factual claim in that context "
    "and do not invent unsupported facts, numbers, or document details. "
    "Retrieve returns only a small adaptive chunk budget (not the whole file) to control "
    "token cost. If a survey-style answer is incomplete, say so and suggest asking about "
    "one case or section at a time — that is an intentional demo limit, not missing files. "
    "When the retrieval budget note says the demo capped top_k, open the answer with a "
    "one-sentence caveat that coverage may be partial for that reason. "
    "If retrieve_documents returns no relevant passages, say clearly that the uploaded "
    "files do not contain the answer. Do not invent document citations or pretend a "
    "passage was found. Prefer answer_directly or web_search only when appropriate; "
    "never fabricate content as if it came from the user's files. "
    "If context is insufficient, say you do not know. "
    "You may receive prior conversation turns. Resolve pronouns and follow-ups from that "
    "history (for example 'he', 'she', 'that resume', 'the person above'). "
    "Prior turns may be in a different language — still answer the latest question in "
    "that question's language. "
    "If a follow-up still needs facts from uploaded files, call retrieve_documents again "
    "with a clear search query; otherwise answer using the prior turns."
)

_DOCUMENT_QUESTION_HINTS = (
    "document",
    "documents",
    "file",
    "files",
    "pdf",
    "upload",
    "uploaded",
    "case",
    "cases",
    "caso",
    "casos",
    "chapter",
    "section",
    "policy",
    "contract",
    "resume",
    "cv",
    "excerpt",
    "passage",
    "according to",
    "in the doc",
    "del documento",
    "el documento",
    "este archivo",
)


def resolve_route(tools_used: list[str]) -> str:
    names = set(tools_used)
    has_retrieve = "retrieve_documents" in names
    has_web = "web_search" in names
    has_direct = "answer_directly" in names
    if has_retrieve and has_web:
        return "mixed"
    if has_retrieve:
        return "retrieve"
    if has_web:
        return "web"
    if has_direct:
        return "direct"
    return "direct"


class AgentService:
    def __init__(
        self,
        rag_service: RAGService,
        settings: Settings | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self.rag_service = rag_service
        self.settings = settings or get_settings()
        self.llm = llm

    async def answer_question(
        self,
        user: User,
        question: str,
        *,
        chat_id: uuid.UUID | None = None,
        model_mode: str = "auto",
        model_name: str | None = None,
        history: list[ConversationTurn] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> QueryResponse:
        async def emit(title: str, detail: str = "") -> None:
            if on_progress:
                await on_progress(title, detail)

        prior = _trim_history(history or [], self.settings.conversation_history_max_turns)
        await emit("Inspect question", "Choosing a model for this ask")
        selection_text = _selection_text(question, prior)
        selection = select_model(
            selection_text,
            self.settings,
            requested_mode=model_mode,
            requested_model=model_name,
        )
        await emit(
            "Picked model",
            f"{selection.provider} / {selection.model}",
        )
        llm = self.llm or get_llm_provider(
            self.settings,
            provider_name=selection.provider,
            model_name=selection.model,
        )
        ready_docs = await _list_ready_documents(self.rag_service, user, chat_id)
        if ready_docs:
            await emit(
                "Chat uploads ready",
                ", ".join(ready_docs[:4]) + ("…" if len(ready_docs) > 4 else ""),
            )
        messages: list[ChatMessage] = [
            ChatMessage(
                role="system",
                content=_system_prompt(selection, ready_docs, question),
            ),
        ]
        for turn in prior:
            messages.append(ChatMessage(role="user", content=turn.question))
            messages.append(ChatMessage(role="assistant", content=turn.answer))
        messages.append(ChatMessage(role="user", content=question))
        context = ToolContext(
            user=user,
            rag_service=self.rag_service,
            chat_id=chat_id,
            tavily_api_key=self.settings.tavily_api_key,
            user_question=question,
        )

        tools_used: list[str] = []
        citations: list[Citation] = []
        seen_citation_keys: set[str] = set()
        retrieval_trace: list[dict] = []
        forced_retrieve_nudge = False

        for _ in range(self.settings.agent_max_tool_rounds):
            if tools_used:
                await emit(
                    "Writing answer",
                    "Grounding the reply in the passages already retrieved",
                )
            else:
                await emit("Planning", "Choosing retrieve, web, or direct")
            result = await llm.chat_with_tools(messages, TOOL_SPECS)
            if not result.tool_calls:
                if (
                    not forced_retrieve_nudge
                    and not tools_used
                    and ready_docs
                    and _looks_like_document_question(question)
                ):
                    forced_retrieve_nudge = True
                    logger.info(
                        "agent_forcing_retrieve_nudge",
                        user_id=str(user.id),
                        chat_id=str(chat_id) if chat_id else None,
                        documents=ready_docs,
                    )
                    await emit(
                        "Nudge retrieve",
                        "Model answered without tools — requiring a document search",
                    )
                    messages.append(
                        ChatMessage(
                            role="assistant",
                            content=(result.content or "").strip()
                            or "(answered without tools)",
                        )
                    )
                    listed = ", ".join(ready_docs)
                    messages.append(
                        ChatMessage(
                            role="user",
                            content=(
                                "You answered without tools, but this chat has uploaded "
                                f"document(s) ready for retrieval: {listed}. "
                                "Call retrieve_documents now with a search query derived "
                                "from my question, then answer only from those passages. "
                                "Do not ask which document if only one file is listed."
                            ),
                        )
                    )
                    continue

                answer = (result.content or "").strip()
                if not answer:
                    answer = "I could not produce an answer."
                route = resolve_route(tools_used)
                logger.info(
                    "agent_query_completed",
                    user_id=str(user.id),
                    tools_used=tools_used,
                    route=route,
                    citation_count=len(citations),
                )
                return QueryResponse(
                    answer=answer,
                    citations=citations,
                    tools_used=tools_used,
                    route=route,
                    model_mode=selection.requested_mode,
                    model_provider=selection.provider,
                    model_name=selection.model,
                    model_selection_explanation=selection.explanation,
                    retrieval_trace=retrieval_trace or None,
                )

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls,
                )
            )

            for call in result.tool_calls:
                tools_used.append(call.name)
                tool_title = _TOOL_STEP_TITLES.get(call.name, call.name)
                tool_detail = _tool_progress_detail(call.name, call.arguments)
                await emit(tool_title, tool_detail)
                tool_result = await execute_tool(call.name, call.arguments, context)
                await emit(
                    f"{tool_title} done",
                    _tool_result_detail(call.name, tool_result),
                )
                for citation in tool_result.citations:
                    key = _citation_key(citation)
                    if key not in seen_citation_keys:
                        seen_citation_keys.add(key)
                        citations.append(citation)
                if tool_result.retrieval_trace:
                    retrieval_trace.extend(tool_result.retrieval_trace)
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=tool_result.content,
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )

        await emit("Writing answer", "Max tool rounds reached — finalizing")
        final = await llm.chat_with_tools(messages, tools=[])
        answer = (final.content or "").strip() or "I could not produce an answer."
        route = resolve_route(tools_used)
        logger.info(
            "agent_query_completed_max_rounds",
            user_id=str(user.id),
            tools_used=tools_used,
            route=route,
        )
        return QueryResponse(
            answer=answer,
            citations=citations,
            tools_used=tools_used,
            route=route,
            model_mode=selection.requested_mode,
            model_provider=selection.provider,
            model_name=selection.model,
            model_selection_explanation=selection.explanation,
            retrieval_trace=retrieval_trace or None,
        )


def _tool_progress_detail(name: str, arguments: dict) -> str:
    query = str(arguments.get("query") or "").strip()
    if name == "retrieve_documents" and query:
        return f'query “{query[:120]}”'
    if name == "web_search" and query:
        return f'query “{query[:120]}”'
    if name == "answer_directly":
        reason = str(arguments.get("reason") or "").strip()
        return reason[:160] if reason else "general knowledge"
    return ""


def _tool_result_detail(name: str, tool_result) -> str:
    if name == "retrieve_documents":
        count = len(tool_result.citations)
        if count:
            return f"{count} citation(s) from uploads"
        if "Already retrieved" in tool_result.content:
            return "skipped duplicate search"
        if "Survey retrieve budget" in tool_result.content:
            return "survey retrieve cap reached"
        return "no matching passages"
    if name == "web_search":
        count = len(tool_result.citations)
        return f"{count} web result(s)" if count else "no web hits"
    return "ok"


def _citation_key(citation: Citation) -> str:
    if citation.source_type == "web":
        return f"web:{citation.url or citation.excerpt[:80]}"
    return f"doc:{citation.chunk_id or citation.excerpt[:80]}"


def _trim_history(
    history: list[ConversationTurn],
    max_turns: int,
) -> list[ConversationTurn]:
    if max_turns <= 0:
        return []
    trimmed = history[-max_turns:]
    return [
        ConversationTurn(
            question=turn.question.strip()[:2000],
            answer=turn.answer.strip()[:4000],
        )
        for turn in trimmed
        if turn.question.strip() and turn.answer.strip()
    ]


def _selection_text(question: str, history: list[ConversationTurn]) -> str:
    if not history:
        return question
    recent = history[-2:]
    prior = " ".join(f"{turn.question} {turn.answer[:400]}" for turn in recent)
    return f"{prior}\n{question}"


def _system_prompt(
    selection: ModelSelection,
    ready_docs: list[str],
    question: str,
) -> str:
    if ready_docs:
        listed = ", ".join(ready_docs)
        upload_context = (
            f"This chat has uploaded document(s) ready for retrieval: {listed}. "
            "When the user refers to the document/file/PDF/cases in this chat, call "
            "retrieve_documents first. Do not ask which file if only one is listed."
        )
    else:
        upload_context = (
            "This chat currently has no ready uploaded documents. "
            "If the user asks about an upload that is missing, say so and ask them to "
            "upload a file before retrieve_documents can help."
        )
    clipped = " ".join(question.strip().split())
    if len(clipped) > 220:
        clipped = f"{clipped[:220]}…"
    language_lock = (
        f"Latest user question: «{clipped}». "
        "Reply language lock: the full final answer must match that question's language "
        "(not the upload language, not earlier turns)."
    )
    return (
        f"{SYSTEM_PROMPT} {upload_context} "
        f"Model selection context: {selection.explanation} "
        "If the user asks why a model or tool was chosen, explain this decision process "
        "briefly without mentioning private API keys or internal settings. "
        f"{language_lock}"
    )


def _looks_like_document_question(question: str) -> bool:
    lowered = question.lower()
    return any(hint in lowered for hint in _DOCUMENT_QUESTION_HINTS)


async def _list_ready_documents(
    rag_service: RAGService,
    user: User,
    chat_id: uuid.UUID | None,
) -> list[str]:
    if chat_id is None:
        return []
    db = getattr(rag_service, "db", None)
    if db is None:
        return []
    try:
        result = await db.execute(
            select(Document.filename)
            .where(
                Document.user_id == user.id,
                Document.chat_id == chat_id,
                Document.status == "ready",
            )
            .order_by(Document.created_at.asc())
        )
        return [str(name) for name in result.scalars().all() if name]
    except Exception:
        logger.exception(
            "chat_document_inventory_failed",
            user_id=str(user.id),
            chat_id=str(chat_id),
        )
        return []
