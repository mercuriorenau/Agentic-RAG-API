import { useState } from "react";
import { Citation } from "../api";
import { CITATIONS } from "../explainers";
import { displayDocumentName } from "../documentNames";
import { Explainer } from "./Explainer";

type Props = {
  citations: Citation[];
};

export function Citations({ citations }: Props) {
  const [open, setOpen] = useState(false);

  if (citations.length === 0) {
    return null;
  }

  const count = citations.length;
  const label = count === 1 ? "1 citation" : `${count} citations`;

  return (
    <div className="citations">
      <div className="citations-head">
        <button
          type="button"
          className="citations-toggle linkish"
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          {open ? `Hide citations ▾` : `Show ${label} ▸`}
        </button>
        <Explainer summary="What citations are">{CITATIONS}</Explainer>
      </div>
      {open ? (
        <ul>
          {citations.map((citation, index) => (
            <li key={`${citation.chunk_id || citation.url || citation.excerpt}-${index}`}>
              <div className="citation-head">
                <span className="badge subtle">{citation.source_type}</span>
                {citation.document_name ? (
                  <strong>{displayDocumentName(citation.document_name)}</strong>
                ) : null}
                {citation.page_number != null ? (
                  <span className="muted">page {citation.page_number}</span>
                ) : null}
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
      ) : null}
    </div>
  );
}
