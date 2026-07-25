export type TourStep = {
  id: string;
  title: string;
  body: string;
  target?: string;
};

export const TOUR_INVITE = {
  title: "Want a quick walkthrough?",
  body:
    "This project exists so more people can see how an AI agent actually works with RAG. " +
    "Each chat owns its documents, and an agent decides when to retrieve from your files, search the web, or answer directly. " +
    "Every panel has a dashed i icon with the technical detail behind it, so open those as you explore. " +
    "Retrieval is intentionally capped for demo token cost, so prefer short PDFs or questions about one section at a time. " +
    "I can show you the flow in about a minute.",
  acceptLabel: "Take the guide",
  declineLabel: "Skip for now",
};

/** Condensed guide after the user accepts the invite. Keep it short. */
export const TOUR_STEPS: TourStep[] = [
  {
    id: "chats",
    title: "Flip for chat history",
    body:
      "After you sign in you already have a workspace. The front shows its files and title; " +
      "use the U-turn to flip to All chats, create another workspace, or reopen one. " +
      "Each chat keeps its own files and message history.",
    target: '[data-tour="new-chat"], [data-tour="chat-history"]',
  },
  {
    id: "documents",
    title: "Upload & index",
    body:
      "Files are split into chunks with page numbers when available, embedded, and indexed in Postgres/pgvector " +
      "with full-text search. Ask uses hybrid retrieval, not a full reread. Prefer " +
      "~15 pages or questions about one section at a time for this demo’s top_k cap.",
    target: '[data-tour="upload-doc"]',
  },
  {
    id: "ask",
    title: "Ask the agent",
    body:
      "The agent picks retrieve_documents, web_search, or answer_directly. Retrieve uses adaptive top_k (max 8) so surveys of long documents stay within the token budget.",
    target: '[data-tour="ask-button"]',
  },
  {
    id: "tech-notes",
    title: "Open the dashed info icons",
    body:
      "This is where the learning happens. Tap any dashed i for technical notes on chats, uploads, " +
      "models, memory, citations, and the retrieval budget. Each one explains a real piece of the " +
      "RAG pipeline in plain language, so open them as you go instead of skipping past.",
    target: '[data-tour="tech-note"]',
  },
  {
    id: "answers",
    title: "Traceable answers",
    body:
      "Each reply shows route, model, tool call counts, citations, and a search log " +
      "(Self-RAG grades, top_k, candidates, rerank) so you can verify what the agent used. " +
      "Expand those sections to watch the agent reason instead of taking the answer on faith.",
    target: '[data-tour="turns"]',
  },
];
