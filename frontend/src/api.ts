export type Citation = {
  source_type: string;
  document_id?: string | null;
  document_name?: string | null;
  chunk_id?: string | null;
  excerpt: string;
  score?: number | null;
  url?: string | null;
};

export type DocumentItem = {
  id: string;
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
};

const TOKEN_KEY = "rag_access_token";
const HISTORY_MAX_TURNS = 6;

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
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
}

export async function listDocuments(): Promise<DocumentItem[]> {
  const data = await request<{ documents: DocumentItem[] }>("/api/v1/documents", {}, true);
  return data.documents;
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData();
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
        question,
        model_mode: modelMode,
        model_name: modelName?.trim() || null,
        history,
      }),
    },
    true,
  );
}
