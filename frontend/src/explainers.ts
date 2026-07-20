import type { QueryResponse } from "./api";

/** Edit these strings freely — the UI imports from this file only. */

export const INTRO =
  "Sign in so your uploads stay under your account. The API uses JWT auth; " +
  "each chat only searches the documents you uploaded into that chat.";

export const DOC_UPLOAD =
  "On upload we extract text (page-aware for PDFs), split it into paragraph-aware " +
  "overlapping chunks, embed each chunk, and store vectors in Postgres with pgvector. " +
  "Questions use hybrid search (vector + full-text), a score floor, and optional LLM " +
  "reranking — not a full re-read of every file.";

export const MODEL_PICKER =
  "Auto looks at the wording of the question and picks a configured provider. " +
  "Or lock OpenAI / Anthropic (and a specific model) yourself. Either way, the " +
  "agent still chooses tools: retrieve documents, web search, or answer directly.";

export const COST_GUARDRAIL =
  "Demo limit: 600 characters per question and 3 asks per IP per day. " +
  "That keeps public traffic from burning through API credits.";

export const CONVERSATION_MEMORY =
  "Follow-ups use the last few Q&A turns, so pronouns like \"he\" or \"that resume\" " +
  "can refer to what you just discussed. Start a fresh question if you want a clean slate.";

export const CHAT_SESSIONS =
  "Each chat keeps its own documents and message history. Switch chats to isolate " +
  "topics — a resume thread will not pull chunks from a policy thread.";

export const CITATIONS =
  "Each card is a source the model actually saw — a document chunk (with page when " +
  "known) or a web snippet. The score reflects retrieval ranking after hybrid search " +
  "and optional rerank (higher is stronger).";

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

  return {
    title: "What just happened",
    paragraphs,
  };
}

function routeParagraph(route: string): string {
  switch (route) {
    case "retrieve":
      return (
        "This question used document retrieval. The agent asked for relevant chunks, " +
        "then wrote the answer from those passages."
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
