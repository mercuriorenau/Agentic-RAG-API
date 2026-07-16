import { Citation } from "../api";
import { CITATIONS } from "../explainers";
import { Explainer } from "./Explainer";

type Props = {
  citations: Citation[];
};

export function Citations({ citations }: Props) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <div className="citations">
      <h3>Citations</h3>
      <Explainer>{CITATIONS}</Explainer>
      <ul>
        {citations.map((citation, index) => (
          <li key={`${citation.chunk_id || citation.url || citation.excerpt}-${index}`}>
            <div className="citation-head">
              <span className="badge subtle">{citation.source_type}</span>
              {citation.document_name ? <strong>{citation.document_name}</strong> : null}
              {citation.score != null ? (
                <span className="muted">score {citation.score.toFixed(3)}</span>
              ) : null}
            </div>
            <p>{citation.excerpt}</p>
            {citation.url ? (
              <a href={citation.url} target="_blank" rel="noreferrer">
                {citation.url}
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
