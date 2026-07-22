export type TourStep = {
  id: string;
  title: string;
  body: string;
  target?: string;
};

export const TOUR_INVITE = {
  title: "Want a quick walkthrough?",
  body:
    "This project is an agentic RAG demo: each chat owns its documents, and an agent decides when to retrieve from your files, search the web, or answer directly. " +
    "Retrieval is intentionally capped for demo token cost — prefer short PDFs or section-by-section questions. " +
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
      "The front of the card is your active workspace. First-time users see Create new chat. " +
      "Once you have chats, the U-turn control flips to the list on the back.",
    target: '[data-tour="new-chat"], [data-tour="chat-history"]',
  },
  {
    id: "documents",
    title: "Upload & index",
    body:
      "Files are chunked, embedded, and stored in Postgres/pgvector. Later questions search those vectors — not the whole file. Prefer ~15 pages or less for this demo’s retrieval budget.",
    target: '[data-tour="upload-doc"]',
  },
  {
    id: "ask",
    title: "Ask the agent",
    body:
      "The agent picks retrieve_documents, web_search, or answer_directly. Retrieve uses adaptive top_k (max 8) so long-document surveys stay token-safe.",
    target: '[data-tour="ask-button"]',
  },
  {
    id: "tech-notes",
    title: "Dashed info icons",
    body:
      "Tap a dashed i for technical notes — chats, uploads, models, memory, citations, and the retrieval budget. They stay tucked away until you want the detail.",
    target: '[data-tour="tech-note"]',
  },
  {
    id: "answers",
    title: "Traceable answers",
    body:
      "Each reply shows route, model, citations, and retrieval attempts (including adaptive top_k) so you can verify what the agent used.",
    target: '[data-tour="turns"]',
  },
];
