export type Citation = {
  source_type: string;
  document_id?: string | null;
  document_name?: string | null;
  chunk_id?: string | null;
  page_number?: number | null;
  excerpt: string;
  score?: number | null;
  url?: string | null;
};

export type ChatItem = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  role: string;
  content: string;
  metadata?: Record<string, unknown> | null;
  created_at: string;
};

export type DocumentItem = {
  id: string;
  chat_id: string;
  filename: string;
  content_type: string;
  status: string;
  created_at: string;
};

export type ModelOption = {
  id: string;
  label: string;
  mode: string;
  provider?: string | null;
  model_name?: string | null;
};

export type ConversationTurn = {
  question: string;
  answer: string;
};

export type QueryResponse = {
  answer: string;
  citations: Citation[];
  tools_used: string[];
  route: string;
  model_mode: string;
  model_provider: string;
  model_name: string;
  model_selection_explanation: string;
  retrieval_trace?: { query: string; grade: string; chunk_count: number }[] | null;
};

const TOKEN_KEY = "rag_access_token";
const USER_EMAIL_KEY = "rag_user_email";
const HISTORY_MAX_TURNS = 6;

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_EMAIL_KEY);
}

export function getUserKey(): string | null {
  return sessionStorage.getItem(USER_EMAIL_KEY);
}

function setUserKey(email: string): void {
  sessionStorage.setItem(USER_EMAIL_KEY, email.toLowerCase());
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = false,
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getToken();
    if (!token) {
      throw new Error("Not authenticated");
    }
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        detail = body.detail
          .map((item: { msg?: string }) => item.msg || "error")
          .join("; ");
      }
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function register(email: string, password: string): Promise<void> {
  await request("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<void> {
  const data = await request<{ access_token: string }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  setUserKey(email);
}

export async function listChats(): Promise<ChatItem[]> {
  const data = await request<{ chats: ChatItem[] }>("/api/v1/chats", {}, true);
  return data.chats;
}

export async function createChat(title = "New chat"): Promise<ChatItem> {
  return request<ChatItem>(
    "/api/v1/chats",
    { method: "POST", body: JSON.stringify({ title }) },
    true,
  );
}

export async function deleteChat(id: string): Promise<void> {
  await request(`/api/v1/chats/${id}`, { method: "DELETE" }, true);
}

export async function listChatMessages(chatId: string): Promise<ChatMessage[]> {
  const data = await request<{ messages: ChatMessage[] }>(
    `/api/v1/chats/${chatId}/messages`,
    {},
    true,
  );
  return data.messages;
}

export async function clearChatMessages(chatId: string): Promise<void> {
  await request(`/api/v1/chats/${chatId}/messages`, { method: "DELETE" }, true);
}

export function turnsFromMessages(
  messages: ChatMessage[],
): { question: string; response: QueryResponse }[] {
  const turns: { question: string; response: QueryResponse }[] = [];
  let pending: string | null = null;
  for (const message of messages) {
    if (message.role === "user") {
      pending = message.content;
      continue;
    }
    if (message.role === "assistant" && pending) {
      const meta = (message.metadata || {}) as Partial<QueryResponse>;
      turns.push({
        question: pending,
        response: {
          answer: message.content,
          citations: (meta.citations as Citation[]) || [],
          tools_used: meta.tools_used || [],
          route: meta.route || "direct",
          model_mode: meta.model_mode || "auto",
          model_provider: meta.model_provider || "openai",
          model_name: meta.model_name || "",
          model_selection_explanation: meta.model_selection_explanation || "",
          retrieval_trace: meta.retrieval_trace || null,
        },
      });
      pending = null;
    }
  }
  return turns.reverse();
}

export async function listDocuments(chatId: string): Promise<DocumentItem[]> {
  const data = await request<{ documents: DocumentItem[] }>(
    `/api/v1/documents?chat_id=${encodeURIComponent(chatId)}`,
    {},
    true,
  );
  return data.documents;
}

export async function uploadDocument(chatId: string, file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("chat_id", chatId);
  form.append("file", file);
  return request<DocumentItem>(
    "/api/v1/documents",
    { method: "POST", body: form },
    true,
  );
}

export async function deleteDocument(id: string): Promise<void> {
  await request(`/api/v1/documents/${id}`, { method: "DELETE" }, true);
}

export async function fetchDocumentBlob(id: string): Promise<{ blob: Blob; filenameHint: string }> {
  const token = getToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  const response = await fetch(`/api/v1/documents/${id}/file`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Preview failed (${response.status})`);
  }
  const blob = await response.blob();
  return { blob, filenameHint: id };
}

export async function listModels(): Promise<ModelOption[]> {
  const data = await request<{ models: ModelOption[] }>("/api/v1/models");
  return data.models;
}

export function historyFromTurns(
  turnsNewestFirst: { question: string; response: QueryResponse }[],
): ConversationTurn[] {
  return [...turnsNewestFirst]
    .reverse()
    .slice(-HISTORY_MAX_TURNS)
    .map((turn) => ({
      question: turn.question,
      answer: turn.response.answer,
    }));
}

export async function askQuestion(
  chatId: string,
  question: string,
  modelMode: string,
  modelName?: string | null,
  history: ConversationTurn[] = [],
): Promise<QueryResponse> {
  return request<QueryResponse>(
    "/api/v1/queries",
    {
      method: "POST",
      body: JSON.stringify({
        chat_id: chatId,
        question,
        model_mode: modelMode,
        model_name: modelName?.trim() || null,
        history,
      }),
    },
    true,
  );
}
