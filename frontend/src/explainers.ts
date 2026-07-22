import type { QueryResponse } from "./api";

/** Edit these strings freely — the UI imports from this file only. */

export const INTRO =
  "Sign in with email or Google so uploads stay under your account (JWT sessions). " +
  "Each chat only searches the documents you uploaded into that chat — never other threads.";

export const DOC_UPLOAD =
  "On upload we extract text (page-aware for PDFs), split it into paragraph-aware " +
  "overlapping chunks (~800 chars, 100 overlap), embed with text-embedding-3-small, " +
  "and store vectors in Postgres with pgvector. Ask uses hybrid search (dense + full-text), " +
  "RRF fusion, a score floor, optional LLM rerank, and Self-RAG grade/rewrite — " +
  "not a full re-read of every file.";

export const RETRIEVAL_BUDGET =
  "Retrieval is adaptive but capped: focused questions use TOP_K (default 5); " +
  "broad ones (e.g. “each case”, “summarize the document”) may rise toward TOP_K_MAX " +
  "(default 8). That keeps demo token spend in check. Incomplete surveys of long PDFs " +
  "are an intentional budget, not a broken index — ask one section at a time for detail.";

/** Visible in-app warning — keep in sync with TOP_K_MAX / chunk defaults. */
export const DOC_SIZE_WARNING_TITLE = "Retrieval budget warning";

export const DOC_SIZE_WARNING =
  "This demo retrieves at most ~8 passages per question (not the whole file) so API " +
  "tokens stay bounded. Best results: PDFs or notes under about 15 pages. Longer docs " +
  "still work if you ask about one case or section at a time — incomplete “cover " +
  "everything” answers are an intentional cost limit, not a bug.";

export const MODEL_PICKER =
  "Auto inspects the question and picks OpenAI or Anthropic from the configured catalog. " +
  "Or lock a provider/model yourself. Either way, the agent still chooses tools: " +
  "retrieve documents, Tavily web search, or answer directly.";

export const COST_GUARDRAIL =
  "Demo limits: 600 characters per question and 3 asks per IP per day, plus the " +
  "retrieval chunk cap above. That keeps public traffic from burning through API credits.";

export const CONVERSATION_MEMORY =
  "Follow-ups use the last few Q&A turns, so pronouns like \"he\" or \"that resume\" " +
  "can refer to what you just discussed. Clear chat memory or start a fresh question " +
  "for a clean slate.";

export const CHAT_SESSIONS =
  "Each chat keeps its own documents and message history. Switch chats to isolate " +
  "topics — a resume thread will not pull chunks from a policy thread.";


  "Each card is a source the model actually saw — a document chunk (with page when " +
  "known) or a web snippet. The score reflects retrieval ranking after hybrid search " +
  "and optional rerank (higher is stronger). Retrieval attempts may show adaptive top_k.";

export type AnswerExplainer = {
  title: string;
  paragraphs: string[];
};

export function explainAnswer(response: QueryResponse): AnswerExplainer {
  const paragraphs: string[] = [];
  const tools = response.tools_used.length
    ? response.tools_used.join(", ")
    : "none (model answered without a tool call)";

  paragraphs.push(routeParagraph(response.route));
  paragraphs.push(`Tools used this turn: ${tools}.`);

  if (response.citations.length > 0) {
    paragraphs.push(
      `It returned ${response.citations.length} citation(s). Open those cards to see ` +
        "the exact passage or URL behind the answer.",
    );
  } else {
    paragraphs.push(
      "No citations this time — usual for direct answers, or when retrieval/web returned nothing useful.",
    );
  }

  paragraphs.push(
    `Model: ${response.model_provider} / ${response.model_name} ` +
      `(mode: ${response.model_mode}).`,
  );

  if (response.model_selection_explanation) {
    paragraphs.push(`Why this model. ${response.model_selection_explanation}`);
  }

  if (response.retrieval_trace && response.retrieval_trace.length > 0) {
    const last = response.retrieval_trace[response.retrieval_trace.length - 1];
    paragraphs.push(
      `Retrieval budget this turn: ${last.chunk_count} chunk(s)` +
        (last.top_k ? ` with adaptive top_k=${last.top_k}` : "") +
        ". Broad questions may miss sections on purpose — ask one case/section for more.",
    );
  }

  return {
    title: "What just happened",
    paragraphs,
  };
}

function routeParagraph(route: string): string {
  switch (route) {
    case "retrieve":
      return (
        "This question used document retrieval. The agent asked for relevant chunks " +
        "(adaptive top_k, capped), then wrote the answer from those passages."
      );
    case "web":
      return (
        "This needed information outside your uploads, so the agent called web search " +
        "and grounded the answer on those results."
      );
    case "mixed":
      return (
        "This turn mixed sources — both document retrieval and web search ran before " +
        "the final answer."
      );
    case "direct":
    default:
      return (
        "No document lookup here. The agent decided general knowledge was enough, " +
        "so it skipped retrieval and web search."
      );
  }
}
