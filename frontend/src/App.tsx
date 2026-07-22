import { FormEvent, useEffect, useState } from "react";
import {
  askQuestion,
  ChatItem,
  clearChatMessages,
  clearToken,
  createChat,
  deleteChat,
  deleteDocument,
  DocumentItem,
  getToken,
  getUserKey,
  historyFromTurns,
  listChatMessages,
  listChats,
  listDocuments,
  listModels,
  login,
  ModelOption,
  QueryResponse,
  register,
  setToken,
  setUserKey as persistUserKey,
  turnsFromMessages,
  uploadDocument,
} from "./api";
import { AuthForm } from "./components/AuthForm";
import { Citations } from "./components/Citations";
import { DocumentPanel } from "./components/DocumentPanel";
import { AnswerExplainerBlock, Explainer } from "./components/Explainer";
import { ProductTour, TourMode } from "./components/ProductTour";
import { RetrievalTrace } from "./components/RetrievalTrace";
import { TourLauncher } from "./components/TourLauncher";
import {
  CHAT_SESSIONS,
  CONVERSATION_MEMORY,
  COST_GUARDRAIL,
  DOC_SIZE_WARNING,
  DOC_SIZE_WARNING_TITLE,
  explainAnswer,
  INTRO,
  MODEL_PICKER,
  RETRIEVAL_BUDGET,
} from "./explainers";
import { clearTourComplete, hasCompletedTour, markTourComplete } from "./tour/tourStorage";

type ChatTurn = {
  question: string;
  response: QueryResponse;
};

const FALLBACK_MODELS: ModelOption[] = [
  {
    id: "auto",
    label: "Auto (inspect question, then choose)",
    mode: "auto",
    provider: null,
    model_name: null,
  },
];

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [question, setQuestion] = useState("");
  const [modelOptions, setModelOptions] = useState<ModelOption[]>(FALLBACK_MODELS);
  const [selectedModelId, setSelectedModelId] = useState("auto");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userKey, setUserKey] = useState(getUserKey());
  const [tourMode, setTourMode] = useState<TourMode | null>(null);

  async function refreshChats(preferredId?: string | null) {
    const items = await listChats();
    setChats(items);
    const nextId =
      (preferredId && items.some((chat) => chat.id === preferredId) && preferredId) ||
      (activeChatId && items.some((chat) => chat.id === activeChatId) && activeChatId) ||
      items[0]?.id ||
      null;
    setActiveChatId(nextId);
    return nextId;
  }

  async function loadChat(chatId: string) {
    const [docs, messages] = await Promise.all([
      listDocuments(chatId),
      listChatMessages(chatId),
    ]);
    setDocuments(docs);
    setTurns(turnsFromMessages(messages));
  }

  async function refreshModels() {
    const models = await listModels();
    setModelOptions(models.length > 0 ? models : FALLBACK_MODELS);
    setSelectedModelId((current) =>
      models.some((model) => model.id === current) ? current : "auto",
    );
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("auth_token");
    const email = params.get("auth_email");
    const authError = params.get("auth_error");
    if (authError) {
      setError(authError);
      window.history.replaceState({}, "", window.location.pathname);
      return;
    }
    if (token) {
      setToken(token);
      if (email) {
        persistUserKey(email);
        setUserKey(email.toLowerCase());
      }
      setAuthed(true);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  useEffect(() => {
    refreshModels().catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!authed) {
      return;
    }
    refreshChats().catch((err: Error) => setError(err.message));
  }, [authed]);

  useEffect(() => {
    if (!authed || !userKey || hasCompletedTour(userKey)) {
      return;
    }
    setTourMode("invite");
  }, [authed, userKey]);

  useEffect(() => {
    if (!authed || !activeChatId) {
      setDocuments([]);
      setTurns([]);
      return;
    }
    loadChat(activeChatId).catch((err: Error) => setError(err.message));
  }, [authed, activeChatId]);

  async function handleAuth(mode: "login" | "register", email: string, password: string) {
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") {
        await register(email, password);
      }
      await login(email, password);
      setUserKey(email.toLowerCase());
      setAuthed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  function handleLogout() {
    clearToken();
    setAuthed(false);
    setUserKey(null);
    setTourMode(null);
    setChats([]);
    setActiveChatId(null);
    setDocuments([]);
    setTurns([]);
    setError(null);
  }

  async function handleNewChat() {
    setError(null);
    setBusy(true);
    try {
      const chat = await createChat();
      await refreshChats(chat.id);
      setDocuments([]);
      setTurns([]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create chat");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteChat(chatId: string) {
    setError(null);
    setBusy(true);
    try {
      await deleteChat(chatId);
      const nextId = await refreshChats(null);
      if (nextId) {
        await loadChat(nextId);
      } else {
        const created = await createChat();
        await refreshChats(created.id);
        setDocuments([]);
        setTurns([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete chat");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(file: File) {
    if (!activeChatId) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await uploadDocument(activeChatId, file);
      setDocuments(await listDocuments(activeChatId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string) {
    if (!activeChatId) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await deleteDocument(id);
      setDocuments(await listDocuments(activeChatId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleClearMemory() {
    if (!activeChatId) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await clearChatMessages(activeChatId);
      setTurns([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear chat memory");
    } finally {
      setBusy(false);
    }
  }

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || !activeChatId) {
      return;
    }
    const selected =
      modelOptions.find((option) => option.id === selectedModelId) || FALLBACK_MODELS[0];
    setError(null);
    setBusy(true);
    try {
      const history = historyFromTurns(turns);
      const response = await askQuestion(
        activeChatId,
        trimmed,
        selected.mode,
        selected.model_name,
        history,
      );
      setTurns((prev) => [{ question: trimmed, response }, ...prev]);
      setQuestion("");
      const items = await listChats();
      setChats(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setBusy(false);
    }
  }

  function handleTourClose() {
    markTourComplete(userKey);
    setTourMode(null);
  }

  function handleTourComplete() {
    markTourComplete(userKey);
    setTourMode(null);
  }

  function handleAcceptInvite() {
    setTourMode("guide");
  }

  function handleDeclineInvite() {
    markTourComplete(userKey);
    setTourMode(null);
  }

  function handleStartTour() {
    setTourMode("guide");
  }

  function handleSimulateFirstVisit() {
    clearTourComplete(userKey);
    setTourMode("invite");
  }

  if (!authed) {
    return (
      <div className="shell auth-screen">
        <div className="auth-screen-inner">
          <header className="hero auth-hero">
            <div className="label-with-note">
              <p className="brand">Agentic RAG</p>
              <Explainer summary="About this demo">{INTRO}</Explainer>
            </div>
            <h1>Ask your documents. Trace every answer.</h1>
            <p className="lede">
              Upload files, then let an agent choose retrieval, web search, or a direct answer —
              with citations you can verify.
            </p>
          </header>
          <AuthForm busy={busy} error={error} onSubmit={handleAuth} />
        </div>
      </div>
    );
  }

  return (
    <div className="shell workspace">
      <header className="topbar">
        <div>
          <p className="brand">Agentic RAG</p>
          <p className="muted">Separate chats, each with its own documents</p>
        </div>
        <button type="button" className="ghost" data-tour="sign-out" onClick={handleLogout}>
          Sign out
        </button>
      </header>

      {error ? <div className="banner error">{error}</div> : null}

      <div className="workspace-grid">
        <div className="chats-column">
        <aside className="panel chats-panel">
          <div className="panel-head">
            <div className="panel-title">
              <h2>Chats</h2>
              <Explainer summary="Why separate chats" tourAnchor>
                {CHAT_SESSIONS}
              </Explainer>
            </div>
            <button
              type="button"
              className="ghost"
              data-tour="new-chat"
              disabled={busy}
              onClick={handleNewChat}
            >
              New
            </button>
          </div>
          {chats.length === 0 ? (
            <p className="muted">Create a chat to upload documents and ask questions.</p>
          ) : (
            <ul className="chat-list">
              {chats.map((chat) => {
                const isActive = chat.id === activeChatId;
                return (
                  <li key={chat.id} className={isActive ? "active chat-block" : "chat-block"}>
                    <div className="chat-row">
                      <button
                        type="button"
                        className="chat-select"
                        data-tour={isActive ? "chat-select" : undefined}
                        disabled={busy}
                        onClick={() => setActiveChatId(chat.id)}
                      >
                        {chat.title}
                      </button>
                      <button
                        type="button"
                        className="linkish danger"
                        data-tour={isActive ? "delete-chat" : undefined}
                        disabled={busy}
                        onClick={() => handleDeleteChat(chat.id)}
                      >
                        Delete
                      </button>
                    </div>
                    {isActive ? (
                      <DocumentPanel
                        documents={documents}
                        busy={busy || !activeChatId}
                        onUpload={handleUpload}
                        onDelete={handleDelete}
                      />
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </aside>
          <aside className="callout warning" role="status">
            <strong>{DOC_SIZE_WARNING_TITLE}</strong>
            <p>{DOC_SIZE_WARNING}</p>
          </aside>
        </div>

        <section className="panel ask-panel">
          <div className="panel-head">
            <div className="panel-title">
              <h2>Ask</h2>
              <Explainer
                summary="How Ask works"
                paragraphs={[COST_GUARDRAIL, RETRIEVAL_BUDGET, CONVERSATION_MEMORY]}
              />
            </div>
            <button
              type="button"
              className="ghost"
              data-tour="clear-memory"
              disabled={busy || turns.length === 0 || !activeChatId}
              onClick={handleClearMemory}
            >
              Clear chat memory
            </button>
          </div>
          <form className="ask-form" onSubmit={handleAsk}>
            <label className="compact-label" data-tour="model-picker">
              <span className="label-with-note">
                Model
                <Explainer summary="Why the model picker matters">{MODEL_PICKER}</Explainer>
              </span>
              <select
                value={selectedModelId}
                onChange={(event) => setSelectedModelId(event.target.value)}
                disabled={busy}
              >
                {modelOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <textarea
              data-tour="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What does the refund policy say?"
              rows={4}
              disabled={busy || !activeChatId}
            />
            <button
              type="submit"
              data-tour="ask-button"
              disabled={busy || !question.trim() || !activeChatId}
            >
              {busy ? "Working…" : "Ask"}
            </button>
          </form>

          <div className="turns" data-tour="turns">
            {turns.length === 0 ? (
              <p className="muted">
                Answers appear here with route, model, citations, and a short walkthrough of
                what the agent did.
              </p>
            ) : (
              turns.map((turn, index) => {
                const walkthrough = explainAnswer(turn.response);
                return (
                  <article key={`${turn.question}-${index}`} className="turn">
                    <p className="question">{turn.question}</p>
                    <div className="turn-meta-row">
                      <div className="meta">
                        <span className="badge">{turn.response.route}</span>
                        <span className="badge">
                          {turn.response.model_provider}: {turn.response.model_name}
                        </span>
                        {turn.response.tools_used.map((tool) => (
                          <span key={tool} className="badge subtle">
                            {tool}
                          </span>
                        ))}
                      </div>
                      <AnswerExplainerBlock
                        title={walkthrough.title}
                        paragraphs={walkthrough.paragraphs}
                        align="end"
                      />
                    </div>
                    <p className="answer">{turn.response.answer}</p>
                    <Citations citations={turn.response.citations} />
                    <RetrievalTrace attempts={turn.response.retrieval_trace} />
                  </article>
                );
              })
            )}
          </div>
        </section>
      </div>
      <TourLauncher
        onStart={handleStartTour}
        onSimulateFirstVisit={handleSimulateFirstVisit}
      />
      <ProductTour
        active={tourMode !== null}
        mode={tourMode || "invite"}
        onClose={handleTourClose}
        onComplete={handleTourComplete}
        onAcceptInvite={handleAcceptInvite}
        onDeclineInvite={handleDeclineInvite}
      />
    </div>
  );
}
