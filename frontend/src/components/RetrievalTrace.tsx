export type RetrievalAttempt = {
  query: string;
  grade: string;
  chunk_count: number;
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
            <span className="retrieval-trace-query">{attempt.query}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
