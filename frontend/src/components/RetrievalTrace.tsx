export type RetrievalAttempt = {
  query: string;
  grade: string;
  chunk_count: number;
  top_k?: number;
};

type Props = {
  attempts: RetrievalAttempt[] | null | undefined;
};

export function RetrievalTrace({ attempts }: Props) {
  if (!attempts || attempts.length === 0) {
    return null;
  }

  return (
    <div className="retrieval-trace">
      <h3>Retrieval attempts</h3>
      <ol>
        {attempts.map((attempt, index) => (
          <li key={`${attempt.query}-${index}`}>
            <span className="badge subtle">{attempt.grade}</span>
            <span className="muted">{attempt.chunk_count} chunks</span>
            {attempt.top_k ? (
              <span className="muted">top_k {attempt.top_k}</span>
            ) : null}
            <span className="retrieval-trace-query">{attempt.query}</span>
          </li>
        ))}
      </ol>
      <p className="retrieval-trace-note muted">
        Adaptive top_k with a hard cap — broad “cover everything” questions may miss
        sections on purpose to limit tokens. Ask one case/section for fuller coverage.
      </p>
    </div>
  );
}
