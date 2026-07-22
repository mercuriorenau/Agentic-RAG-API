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

export const COVERAGE_LIMIT_TITLE = "Partial coverage — demo retrieval limit";

export function coverageNotice(
  response: QueryResponse,
): { title: string; body: string } | null {
  const attempts = response.retrieval_trace;
  if (!attempts || attempts.length === 0) {
    return null;
  }
  if (response.route !== "retrieve" && response.route !== "mixed") {
    return null;
  }

  // Only survey-style asks set budget_capped. Filling top_k on a focused question
  // (e.g. Caso 9 → 5/5) is normal and must NOT show this banner.
  const cappedAttempt = [...attempts]
    .reverse()
    .find((item) => item.budget_capped);
  if (!cappedAttempt) {
    return null;
  }

  const topK = cappedAttempt.top_k ?? cappedAttempt.chunk_count;
  const maxK = cappedAttempt.top_k_max ?? topK;
  const ideal = cappedAttempt.ideal_top_k;
  const filled =
    typeof cappedAttempt.top_k === "number" &&
    cappedAttempt.chunk_count >= cappedAttempt.top_k;

  let body =
    `This was a broad / survey-style question. Each search kept at most top_k=${topK} ` +
    `passages (hard cap TOP_K_MAX=${maxK}), not the whole file. `;
  if (filled) {
    body +=
      `The budget was fully used (${cappedAttempt.chunk_count}/${topK}), so other sections ` +
      `in the upload may be missing from this answer. `;
  } else {
    body +=
      `Coverage can still be incomplete when searches keep hitting the same passages. `;
  }
  if (ideal && topK && ideal > topK) {
    body += `A fuller survey would want about top_k=${ideal}, but this demo caps retrieve to control API cost. `;
  }
  body +=
    `That is an intentional limit — not a broken index. Ask about one case or section ` +
    `(e.g. “Caso 3 Lidl”) for detail the survey may have skipped.`;

  return { title: COVERAGE_LIMIT_TITLE, body };
}

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
  "The front of this card is your active workspace (title + documents). Use the U-turn " +
  "control to flip to the chat list on the back. The last remaining chat has no Delete control so you always keep a workspace. Each chat keeps its own files " +
  "and history so threads never mix retrieval contexts.";

export const CHAT_HISTORY =
  "Past chats live on the back of the card. Create a New chat here, or select one to " +
  "flip back to its documents. Delete appears when more than one chat exists, so the " +
  "last workspace stays available.";

export const CITATIONS =
  "Each card is a source the model actually saw — a document chunk (with page when " +
  "known) or a web snippet. The score reflects retrieval ranking after hybrid search " +
  "and optional rerank (higher is stronger). Retrieval attempts may show adaptive top_k.";

export const AGENT_PATH =
  "Route is the path the agent took: retrieve (uploaded files), web, direct, or mixed. " +
  "The model badge is which LLM ran the agent loop (Auto or your lock). " +
  "Tool chips count each tool call in that loop — retrieve_documents ×9 means nine " +
  "separate searches, not nine models. The agent may search again with a new query " +
  "when coverage looks thin.";

export const RETRIEVAL_ATTEMPTS =
  "This log is the search pipeline inside retrieve_documents. Hybrid search (vector + " +
  "full-text, fused with RRF) builds candidates; an optional LLM reranker reorders them; " +
  "then only top_k passages go to the agent. Self-RAG grades evidence as sufficient, " +
  "partial, or irrelevant — if weak, it rewrites the query and searches again. " +
  "top_k is the adaptive budget for this question (capped for the demo). " +
  "Candidates are how many passages passed the score floor before the final cut.";

export type AnswerExplainer = {
  title: string;
  paragraphs: string[];
};

function summarizeToolCalls(tools: string[]): string {
  if (tools.length === 0) {
    return "none (model answered without a tool call)";
  }
  const counts = new Map<string, number>();
  for (const tool of tools) {
    counts.set(tool, (counts.get(tool) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => (count > 1 ? `${name} ×${count}` : name))
    .join(", ");
}

export function explainAnswer(response: QueryResponse): AnswerExplainer {
  const paragraphs: string[] = [];
  const tools = summarizeToolCalls(response.tools_used);
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
    paragraphs.push(...retrievalWalkthrough(response.retrieval_trace));
  }

  return {
    title: "What just happened",
    paragraphs,
  };
}

function retrievalWalkthrough(
  attempts: NonNullable<QueryResponse["retrieval_trace"]>,
): string[] {
  const last = attempts[attempts.length - 1];
  const lines: string[] = [];
  const topK = last.top_k;
  const base = last.top_k_base;
  const maxK = last.top_k_max;
  const candidates = last.candidate_count;
  const pool = last.candidate_pool_limit;
  const finalChunks = last.chunk_count;

  let budget =
    `Retrieval budget: kept ${finalChunks} final chunk(s)` +
    (topK ? ` with adaptive top_k=${topK}` : "") +
    (base && maxK ? ` (base TOP_K=${base}, hard cap TOP_K_MAX=${maxK})` : "") +
    ".";
  if (typeof candidates === "number") {
    budget +=
      ` Hybrid search scored ${candidates} candidate passage(s)` +
      (pool ? ` from pools of up to ${pool} per channel (dense + full-text, fused with RRF)` : "") +
      " before the final cut.";
  }
  lines.push(budget);

  switch (last.rerank) {
    case "applied":
      lines.push(
        "Rerank: an LLM listwise reranker reordered those candidates by relevance to the question, then the pipeline sliced to top_k.",
      );
      break;
    case "disabled":
      lines.push(
        "Rerank: disabled for this deploy — the pipeline kept hybrid RRF order and sliced to top_k.",
      );
      break;
    case "fail_open":
      lines.push(
        "Rerank: enabled, but the reranker failed open — hybrid order was kept, then sliced to top_k so retrieve still returned passages.",
      );
      break;
    case "skipped":
      lines.push(
        "Rerank: skipped (no candidates passed the score floor), so nothing was reordered.",
      );
      break;
    default:
      if (last.rerank) {
        lines.push(`Rerank status: ${last.rerank}.`);
      }
  }

  if (attempts.length > 1) {
    const grades = attempts.map((item, index) => `pass ${index + 1}=${item.grade}`).join(", ");
    lines.push(
      `Search log: ${attempts.length} pass(es) across retrieve_documents call(s) (${grades}). ` +
        "Later passes may use a rewritten query when Self-RAG graded evidence as thin.",
    );
  } else if (last.grade) {
    lines.push(`Self-RAG evidence grade for this retrieve: ${last.grade}.`);
  }

  if (
    last.budget_capped &&
    typeof last.ideal_top_k === "number" &&
    typeof topK === "number" &&
    last.ideal_top_k > topK
  ) {
    lines.push(
      `Budget note: this question would be better with about top_k=${last.ideal_top_k} ` +
        `passages because it needs wider coverage, but the demo hard-capped retrieve at ` +
        `top_k=${topK}. Ask one case/section at a time for detail the cap may have missed.`,
    );
  }

  return lines;
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
