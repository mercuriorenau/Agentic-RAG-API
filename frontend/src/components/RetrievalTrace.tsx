import { Explainer } from "./Explainer";
import { RETRIEVAL_ATTEMPTS } from "../explainers";

export type RetrievalAttempt = {
  query: string;
  grade: string;
  chunk_count: number;
  top_k?: number;
  top_k_base?: number;
  top_k_max?: number;
  ideal_top_k?: number;
  budget_capped?: boolean;
  candidate_count?: number;
  candidate_pool_limit?: number;
  rerank?: string;
};

type Props = {
  attempts: RetrievalAttempt[] | null | undefined;
};

function gradeBlurb(grade: string): string {
  switch (grade.toLowerCase()) {
    case "sufficient":
      return "Self-RAG judged the passages strong enough to answer.";
    case "partial":
      return "Self-RAG found some signal but coverage looked thin — may rewrite and retry.";
    case "irrelevant":
      return "Self-RAG found little useful evidence — usually rewrites the query and searches again.";
    default:
      return "Self-RAG evidence grade for this search pass.";
  }
}

function rerankBlurb(rerank: string | undefined): string {
  switch (rerank) {
    case "applied":
      return "LLM listwise rerank reordered candidates, then kept top_k.";
    case "disabled":
      return "Rerank off — kept hybrid RRF order, then top_k.";
    case "fail_open":
      return "Rerank failed open — kept hybrid order, then top_k.";
    case "skipped":
      return "Rerank skipped (no candidates after the score floor).";
    default:
      return rerank ? `Rerank: ${rerank}.` : "Rerank status unknown.";
  }
}

export function RetrievalTrace({ attempts }: Props) {
  if (!attempts || attempts.length === 0) {
    return null;
  }

  const last = attempts[attempts.length - 1];
  const capped =
    Boolean(last.budget_capped) &&
    typeof last.ideal_top_k === "number" &&
    typeof last.top_k === "number" &&
    last.ideal_top_k > last.top_k;

  return (
    <div className="retrieval-trace">
      <div className="retrieval-trace-head">
        <h3>How passages were found</h3>
        <Explainer summary="Retrieval pipeline">{RETRIEVAL_ATTEMPTS}</Explainer>
      </div>
      <p className="retrieval-trace-lead muted">
        Each row is one search pass inside <code>retrieve_documents</code> (including
        Self-RAG retries). The agent may call that tool several times; every pass is
        listed here.
      </p>
      <ol>
        {attempts.map((attempt, index) => {
          const topK = attempt.top_k;
          const candidates = attempt.candidate_count;
          return (
            <li key={`${attempt.query}-${index}`} className="retrieval-trace-card">
              <div className="retrieval-trace-card-top">
                <span className="badge subtle">Pass {index + 1}</span>
                <span className={`badge grade-${attempt.grade.toLowerCase()}`}>
                  {attempt.grade}
                </span>
              </div>
              <p className="retrieval-trace-grade-note muted">{gradeBlurb(attempt.grade)}</p>
              <p className="retrieval-trace-query">
                <span className="retrieval-trace-kicker">Search query</span>
                {attempt.query}
              </p>
              <ul className="retrieval-trace-metrics">
                <li>
                  <strong>Budget</strong>
                  <span>
                    kept {attempt.chunk_count}
                    {topK ? ` of top_k=${topK}` : ""} passages for the agent
                    {attempt.top_k_max ? ` (cap ${attempt.top_k_max})` : ""}
                  </span>
                </li>
                <li>
                  <strong>Candidates</strong>
                  <span>
                    {typeof candidates === "number"
                      ? `${candidates} passed the score floor before the final cut`
                      : "not reported"}
                    {attempt.candidate_pool_limit
                      ? ` (pools up to ${attempt.candidate_pool_limit}/channel)`
                      : ""}
                  </span>
                </li>
                <li>
                  <strong>Rerank</strong>
                  <span>{rerankBlurb(attempt.rerank)}</span>
                </li>
              </ul>
            </li>
          );
        })}
      </ol>
      <p className="retrieval-trace-note muted">
        Pipeline: hybrid search (dense vectors + full-text) → RRF fusion → optional
        rerank → keep top_k.
        {capped
          ? ` This survey-style question would be better with about top_k=${last.ideal_top_k}, but the demo hard-capped retrieve at top_k=${last.top_k}.`
          : " Adaptive top_k stays inside the demo hard cap so token spend stays bounded."}
      </p>
    </div>
  );
}
