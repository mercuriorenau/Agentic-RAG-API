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
    "I can show you the flow in about a minute — useful if you want the product story and a bit of the architecture.",
  acceptLabel: "Take the guide",
  declineLabel: "Skip for now",
};

/** Condensed guide after the user accepts the invite. Keep it short. */
export const TOUR_STEPS: TourStep[] = [
  {
    id: "chats",
    title: "Chats are workspaces",
    body:
      "Create a chat per topic. Documents and message history stay scoped to that chat, so retrieval never mixes contexts.",
    target: '[data-tour="new-chat"]',
  },
  {
    id: "documents",
    title: "Upload & index",
    body:
      "Files are extracted, chunked, embedded, and stored in Postgres with pgvector. Later questions search those vectors — not the whole file again.",
    target: '[data-tour="upload-doc"]',
  },
  {
    id: "ask",
    title: "Ask the agent",
    body:
      "The agent picks a tool path: retrieve_documents, web_search, or answer_directly. Auto can also choose a model before that loop runs.",
    target: '[data-tour="ask-button"]',
  },
  {
    id: "tech-notes",
    title: "Dashed info icons",
    body:
      "Tap a dashed i next to a section title for a short technical note — chats, uploads, models, memory, citations, and more. They stay tucked away until you want the detail.",
    target: '[data-tour="tech-note"]',
  },
  {
    id: "answers",
    title: "Traceable answers",
    body:
      "Each reply shows route, model, and citations so you can verify what the agent used.",
    target: '[data-tour="turns"]',
  },
];
