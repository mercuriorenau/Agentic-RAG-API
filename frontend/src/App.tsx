import { FormEvent, useEffect, useState } from "react";
import {
  askQuestion,
  clearToken,
  deleteDocument,
  DocumentItem,
  getToken,
  listDocuments,
  listModels,
  login,
  ModelOption,
  QueryResponse,
  register,
  uploadDocument,
} from "./api";
import { AuthForm } from "./components/AuthForm";
import { Citations } from "./components/Citations";
import { DocumentPanel } from "./components/DocumentPanel";
import { AnswerExplainerBlock, Explainer } from "./components/Explainer";
import {
  COST_GUARDRAIL,
  explainAnswer,
  INTRO,
  MODEL_PICKER,
} from "./explainers";

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
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [question, setQuestion] = useState("");
  const [modelOptions, setModelOptions] = useState<ModelOption[]>(FALLBACK_MODELS);
  const [selectedModelId, setSelectedModelId] = useState("auto");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshDocuments() {
    const docs = await listDocuments();
    setDocuments(docs);
  }

  async function refreshModels() {
    const models = await listModels();
    setModelOptions(models.length > 0 ? models : FALLBACK_MODELS);
    setSelectedModelId((current) =>
      models.some((model) => model.id === current) ? current : "auto",
    );
  }

  useEffect(() => {
    refreshModels().catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!authed) {
      return;
    }
    refreshDocuments().catch((err: Error) => setError(err.message));
  }, [authed]);

  async function handleAuth(mode: "login" | "register", email: string, password: string) {
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") {
        await register(email, password);
      }
      await login(email, password);
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
    setDocuments([]);
    setTurns([]);
    setError(null);
  }

  async function handleUpload(file: File) {
    setError(null);
    setBusy(true);
    try {
      await uploadDocument(file);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string) {
    setError(null);
    setBusy(true);
    try {
      await deleteDocument(id);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      return;
    }
    const selected =
      modelOptions.find((option) => option.id === selectedModelId) || FALLBACK_MODELS[0];
    setError(null);
    setBusy(true);
    try {
      const response = await askQuestion(trimmed, selected.mode, selected.model_name);
      setTurns((prev) => [{ question: trimmed, response }, ...prev]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setBusy(false);
    }
  }

  if (!authed) {
    return (
      <div className="shell">
        <header className="hero">
          <p className="brand">Agentic RAG</p>
          <h1>Ask your documents. Trace every answer.</h1>
          <p className="lede">
            Upload files, then let an agent choose retrieval, web search, or a direct answer —
            with citations you can verify.
          </p>
          <Explainer>{INTRO}</Explainer>
        </header>
        <AuthForm busy={busy} error={error} onSubmit={handleAuth} />
      </div>
    );
  }

  return (
    <div className="shell workspace">
      <header className="topbar">
        <div>
          <p className="brand">Agentic RAG</p>
          <p className="muted">Documents, agent routing, and cited answers</p>
        </div>
        <button type="button" className="ghost" onClick={handleLogout}>
          Sign out
        </button>
      </header>

      {error ? <div className="banner error">{error}</div> : null}

      <div className="grid">
        <DocumentPanel
          documents={documents}
          busy={busy}
          onUpload={handleUpload}
          onDelete={handleDelete}
        />

        <section className="panel ask-panel">
          <h2>Ask</h2>
          <Explainer>{COST_GUARDRAIL}</Explainer>
          <form className="ask-form" onSubmit={handleAsk}>
            <label className="compact-label">
              Model
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
            <Explainer summary="Why the model picker matters">{MODEL_PICKER}</Explainer>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What does the refund policy say?"
              rows={4}
              disabled={busy}
            />
            <button type="submit" disabled={busy || !question.trim()}>
              {busy ? "Working…" : "Ask"}
            </button>
          </form>

          <div className="turns">
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
                      open={index === 0}
                    />
                    <p className="answer">{turn.response.answer}</p>
                    <Citations citations={turn.response.citations} />
                  </article>
                );
              })
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
