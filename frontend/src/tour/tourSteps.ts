export type TourStep = {
  id: string;
  title: string;
  body: string;
  target?: string;
};

export const TOUR_STEPS: TourStep[] = [
  {
    id: "intro",
    title: "Welcome to Agentic RAG",
    body:
      "This app lets you create separate chats, upload documents into each one, and ask an agent that can retrieve, search the web, or answer directly. Dashed info icons explain the technical pieces as you explore.",
  },
  {
    id: "tour-launcher",
    title: "Replay the tour",
    body: "Use this corner control to replay the guide or simulate a first visit for demos.",
    target: '[data-tour="tour-launcher"]',
  },
  {
    id: "sign-out",
    title: "Session control",
    body: "Sign out clears the browser session token. Your chats and documents stay on the server.",
    target: '[data-tour="sign-out"]',
  },
  {
    id: "new-chat",
    title: "New chat",
    body:
      "A chat is an isolated workspace. Documents and message history in one chat do not leak into another.",
    target: '[data-tour="new-chat"]',
  },
  {
    id: "chat-select",
    title: "Switch context",
    body: "Selecting a chat loads only that chat's documents and saved messages.",
    target: '[data-tour="chat-select"]',
  },
  {
    id: "delete-chat",
    title: "Delete chat",
    body: "Deleting a chat removes that chat, its persisted messages, and its uploaded documents.",
    target: '[data-tour="delete-chat"]',
  },
  {
    id: "tech-icons",
    title: "Technical notes",
    body:
      "Dashed info icons open short technical notes about what the app is doing under the hood.",
    target: '[data-tour="tech-note"]',
  },
  {
    id: "upload",
    title: "Upload documents",
    body:
      "Uploads are extracted, chunked, embedded, and stored in pgvector so retrieval can search semantic passages.",
    target: '[data-tour="upload-doc"]',
  },
  {
    id: "preview",
    title: "Preview files",
    body: "Preview streams the original uploaded file back inline so you can verify the source.",
    target: '[data-tour="preview-doc"]',
  },
  {
    id: "remove-doc",
    title: "Remove files",
    body: "Remove deletes this document and its indexed chunks from the active chat.",
    target: '[data-tour="remove-doc"]',
  },
  {
    id: "clear-memory",
    title: "Clear chat memory",
    body: "This clears persisted messages for the active chat without deleting uploaded documents.",
    target: '[data-tour="clear-memory"]',
  },
  {
    id: "model-picker",
    title: "Model picker",
    body:
      "Auto inspects the question before the agent call. You can also lock a provider and model manually.",
    target: '[data-tour="model-picker"]',
  },
  {
    id: "question",
    title: "Question box",
    body: "The public demo caps question length to control token usage and keep API spend predictable.",
    target: '[data-tour="question"]',
  },
  {
    id: "ask",
    title: "Ask button",
    body:
      "The agent decides which tool to call, gathers context, then writes a grounded final answer.",
    target: '[data-tour="ask-button"]',
  },
  {
    id: "turns",
    title: "Answers and citations",
    body:
      "Answers show the route, model, tools used, and citations so you can audit what happened.",
    target: '[data-tour="turns"]',
  },
];
