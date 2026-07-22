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
import { AgentPath } from "./components/AgentPath";
import { Citations } from "./components/Citations";
import { AnswerExplainerBlock, Explainer } from "./components/Explainer";
import { DocumentPanel } from "./components/DocumentPanel";
import { ProductTour, TourMode } from "./components/ProductTour";
import { RetrievalTrace } from "./components/RetrievalTrace";
import { TourLauncher } from "./components/TourLauncher";
import { StackStrip } from "./components/StackStrip";
import { AuthForm } from "./components/AuthForm";
import {
  CHAT_HISTORY,
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
import {
  clearCreateNudgeDone,
  clearTourComplete,
  hasCompletedTour,
  hasDismissedCreateNudge,
  markCreateNudgeDone,
  markTourComplete,
} from "./tour/tourStorage";

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
  const [chatsFlipped, setChatsFlipped] = useState(false);
  const [showCreateNudge, setShowCreateNudge] = useState(false);

  const activeChat = chats.find((chat) => chat.id === activeChatId) ?? null;
  const showCreateChatControl = chats.length === 0;

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
    setChatsFlipped(false);
    setShowCreateNudge(false);
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
      setChatsFlipped(false);
      if (showCreateNudge) {
        dismissCreateNudge();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create chat");
    } finally {
      setBusy(false);
    }
  }

  function handleSelectChat(chatId: string) {
    setActiveChatId(chatId);
    setChatsFlipped(false);
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
        setActiveChatId(null);
        setDocuments([]);
        setTurns([]);
        setQuestion("");
        setChatsFlipped(false);
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

  function finishFirstVisitFlow() {
    markTourComplete(userKey);
    setTourMode(null);
    // After the invite/tour — not during it — nudge first-time users to create a chat.
    if (!hasDismissedCreateNudge(userKey)) {
      setShowCreateNudge(true);
      setChatsFlipped(false);
    }
  }

  function dismissCreateNudge() {
    markCreateNudgeDone(userKey);
    setShowCreateNudge(false);
  }

  function handleTourClose() {
    finishFirstVisitFlow();
  }

  function handleTourComplete() {
    finishFirstVisitFlow();
  }

  function handleAcceptInvite() {
    setTourMode("guide");
  }

  function handleDeclineInvite() {
    finishFirstVisitFlow();
  }

  function handleStartTour() {
    setTourMode("guide");
  }

  function handleSimulateFirstVisit() {
    clearTourComplete(userKey);
    clearCreateNudgeDone(userKey);
    setShowCreateNudge(false);
    setChatsFlipped(false);
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
        <StackStrip />
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
          <div className={`chats-flip${chatsFlipped ? " is-flipped" : ""}`}>
            <div className="chats-flip-inner">
              <aside className="panel chats-panel chats-face chats-face-front">
                <div className="panel-head">
                  <div className="panel-title">
                    <h2>Chats</h2>
                    <Explainer summary="Why separate chats" tourAnchor>
                      {CHAT_SESSIONS}
                    </Explainer>
                  </div>
                  {showCreateChatControl ? (
                    <div className="create-chat-control">
                      <button
                        type="button"
                        className="ghost create-chat-btn"
                        data-tour="new-chat"
                        disabled={busy}
                        onClick={handleNewChat}
                      >
                        <span className="create-chat-icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                            <path d="M12 5v14M5 12h14" />
                          </svg>
                        </span>
                        Create new chat
                      </button>
                      {showCreateNudge && tourMode === null ? (
                        <div className="create-chat-nudge" role="status">
                          <span className="create-chat-nudge-arrow" aria-hidden="true" />
                          <p>Click here to create a new chat</p>
                          <button
                            type="button"
                            className="create-chat-nudge-dismiss"
                            aria-label="Dismiss"
                            onClick={dismissCreateNudge}
                          >
                            ×
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="create-chat-control">
                      <button
                        type="button"
                        className="flip-chat-btn"
                        data-tour="chat-history"
                        disabled={busy}
                        aria-label="Flip to all chats"
                        title="Flip to all chats"
                        onClick={() => {
                        dismissCreateNudge();
                        setChatsFlipped(true);
                      }}
                      >
                        <span className="u-turn-icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M9 14 4 9l5-5" />
                            <path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
                          </svg>
                        </span>
                      </button>
                      {showCreateNudge && tourMode === null ? (
                        <div className="create-chat-nudge" role="status">
                          <span className="create-chat-nudge-arrow" aria-hidden="true" />
                          <p>Click the arrow to flip and create a new chat</p>
                          <button
                            type="button"
                            className="create-chat-nudge-dismiss"
                            aria-label="Dismiss"
                            onClick={dismissCreateNudge}
                          >
                            ×
                          </button>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
                {!activeChat ? (
                  <div className="chat-empty-prompt">
                    <p className="muted">
                      No active chat. Create one here to upload documents and ask — no need to flip the card.
                    </p>
                    <button
                      type="button"
                      className="ghost create-chat-btn"
                      disabled={busy}
                      onClick={handleNewChat}
                    >
                      <span className="create-chat-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                          <path d="M12 5v14M5 12h14" />
                        </svg>
                      </span>
                      Create new chat
                    </button>
                  </div>
                ) : (
                  <div className="chat-block active front-chat">
                    <div className="chat-row">
                      <p className="chat-select front-chat-title" title={activeChat.title}>
                        {activeChat.title}
                      </p>
                      {chats.length > 1 ? (
                        <button
                          type="button"
                          className="linkish danger"
                          data-tour="delete-chat"
                          disabled={busy}
                          onClick={() => handleDeleteChat(activeChat.id)}
                        >
                          Delete
                        </button>
                      ) : null}
                    </div>
                    <DocumentPanel
                      documents={documents}
                      busy={busy || !activeChatId}
                      onUpload={handleUpload}
                      onDelete={handleDelete}
                    />
                  </div>
                )}
              </aside>

              <aside className="panel chats-panel chats-face chats-face-back" aria-hidden={!chatsFlipped}>
                <div className="panel-head">
                  <div className="panel-title">
                    <h2>All chats</h2>
                    <Explainer summary="Chat history">{CHAT_HISTORY}</Explainer>
                  </div>
                  <div className="chats-back-actions">
                    <button
                      type="button"
                      className="ghost create-chat-btn"
                      data-tour="new-chat-back"
                      disabled={busy}
                      onClick={handleNewChat}
                    >
                      <span className="create-chat-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                          <path d="M12 5v14M5 12h14" />
                        </svg>
                      </span>
                      New chat
                    </button>
                    <button
                      type="button"
                      className="flip-chat-btn"
                      disabled={busy}
                      aria-label="Flip back to active chat"
                      title="Flip back"
                      onClick={() => setChatsFlipped(false)}
                    >
                      <span className="u-turn-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M9 14 4 9l5-5" />
                          <path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
                        </svg>
                      </span>
                    </button>
                  </div>
                </div>
                {chats.length === 0 ? (
                  <div className="chat-empty-prompt">
                    <p className="muted">No chats yet. Create one to upload documents and ask.</p>
                    <button
                      type="button"
                      className="ghost create-chat-btn"
                      data-tour="new-chat"
                      disabled={busy}
                      onClick={handleNewChat}
                    >
                      <span className="create-chat-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                          <path d="M12 5v14M5 12h14" />
                        </svg>
                      </span>
                      Create new chat
                    </button>
                  </div>
                ) : (
                  <ul className="chat-list chat-list-back">
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
                              onClick={() => handleSelectChat(chat.id)}
                            >
                              {chat.title}
                            </button>
                            {chats.length > 1 ? (
                              <button
                                type="button"
                                className="linkish danger"
                                disabled={busy}
                                onClick={() => handleDeleteChat(chat.id)}
                              >
                                Delete
                              </button>
                            ) : null}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </aside>
            </div>
          </div>
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
                      <AgentPath
                        route={turn.response.route}
                        modelProvider={turn.response.model_provider}
                        modelName={turn.response.model_name}
                        toolsUsed={turn.response.tools_used}
                      />
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
