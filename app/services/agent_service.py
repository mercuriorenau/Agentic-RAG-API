import uuid

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models import User
from app.schemas.query import Citation, ConversationTurn, QueryResponse
from app.services.llm.base import ChatMessage, LLMProvider
from app.services.llm.factory import get_llm_provider
from app.services.llm.model_selector import ModelSelection, select_model
from app.services.rag_service import RAGService
from app.services.tools import TOOL_SPECS, ToolContext, execute_tool

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are an agent that answers user questions using tools when helpful. "
    "Available tools: retrieve_documents (search uploaded files), web_search "
    "(public web), answer_directly (general knowledge with no external lookup). "
    "Choose the minimum set of tools needed. Prefer retrieve_documents for questions "
    "about the user's documents. Use web_search for current or external facts. "
    "Use answer_directly for greetings, simple definitions, or math that needs no sources. "
    "After tool results arrive, produce a final answer. "
    "When document or web context is provided, ground every factual claim in that context "
    "and do not invent unsupported facts, numbers, or document details. "
    "Retrieve returns only a small adaptive chunk budget (not the whole file) to control "
    "token cost. If a survey-style answer is incomplete, say so and suggest asking about "
    "one case or section at a time — that is an intentional demo limit, not missing files. "
    "If retrieve_documents returns no relevant passages, say clearly that the uploaded "
    "files do not contain the answer. Do not invent document citations or pretend a "
    "passage was found. Prefer answer_directly or web_search only when appropriate; "
    "never fabricate content as if it came from the user's files. "
    "If context is insufficient, say you do not know. "
    "You may receive prior conversation turns. Resolve pronouns and follow-ups from that "
    "history (for example 'he', 'she', 'that resume', 'the person above'). "
    "If a follow-up still needs facts from uploaded files, call retrieve_documents again "
    "with a clear search query; otherwise answer using the prior turns."
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
    ) -> QueryResponse:
        prior = _trim_history(history or [], self.settings.conversation_history_max_turns)
        selection_text = _selection_text(question, prior)
        selection = select_model(
            selection_text,
            self.settings,
            requested_mode=model_mode,
            requested_model=model_name,
        )
        llm = self.llm or get_llm_provider(
            self.settings,
            provider_name=selection.provider,
            model_name=selection.model,
        )
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=_system_prompt(selection)),
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
        )

        tools_used: list[str] = []
        citations: list[Citation] = []
        seen_citation_keys: set[str] = set()
        retrieval_trace: list[dict] = []

        for _ in range(self.settings.agent_max_tool_rounds):
            result = await llm.chat_with_tools(messages, TOOL_SPECS)
            if not result.tool_calls:
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
                tool_result = await execute_tool(call.name, call.arguments, context)
                for citation in tool_result.citations:
                    key = _citation_key(citation)
                    if key not in seen_citation_keys:
                        seen_citation_keys.add(key)
                        citations.append(citation)
                if tool_result.retrieval_trace:
                    retrieval_trace = tool_result.retrieval_trace
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=tool_result.content,
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )

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


def _system_prompt(selection: ModelSelection) -> str:
    return (
        f"{SYSTEM_PROMPT} Model selection context: {selection.explanation} "
        "If the user asks why a model or tool was chosen, explain this decision process "
        "briefly without mentioning private API keys or internal settings."
    )
