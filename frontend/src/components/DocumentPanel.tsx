import { ChangeEvent, useRef } from "react";
import { DocumentItem } from "../api";

type Props = {
  documents: DocumentItem[];
  busy: boolean;
  onUpload: (file: File) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
};

export function DocumentPanel({ documents, busy, onUpload, onDelete }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await onUpload(file);
    event.target.value = "";
  }

  return (
    <section className="panel docs-panel">
      <div className="panel-head">
        <h2>Documents</h2>
        <button type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
          Upload
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md,text/plain,application/pdf,text/markdown"
          hidden
          onChange={handleChange}
        />
      </div>
      {documents.length === 0 ? (
        <p className="muted">Upload a PDF, TXT, or Markdown file to get started.</p>
      ) : (
        <ul className="doc-list">
          {documents.map((doc) => (
            <li key={doc.id}>
              <div>
                <strong>{doc.filename}</strong>
                <span className={`status ${doc.status}`}>{doc.status}</span>
              </div>
              <button
                type="button"
                className="ghost danger"
                disabled={busy}
                onClick={() => onDelete(doc.id)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
