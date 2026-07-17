import { ChangeEvent, useEffect, useRef, useState } from "react";
import { DocumentItem, fetchDocumentBlob } from "../api";
import { DOC_UPLOAD } from "../explainers";
import { Explainer } from "./Explainer";

type Props = {
  documents: DocumentItem[];
  busy: boolean;
  onUpload: (file: File) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
};

type PreviewState = {
  url: string;
  filename: string;
  contentType: string;
  text?: string;
};

export function DocumentPanel({ documents, busy, onUpload, onDelete }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);

  useEffect(() => {
    return () => {
      if (preview?.url) {
        URL.revokeObjectURL(preview.url);
      }
    };
  }, [preview]);

  async function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await onUpload(file);
    event.target.value = "";
  }

  async function handlePreview(doc: DocumentItem) {
    setPreviewError(null);
    setPreviewBusy(true);
    try {
      if (preview?.url) {
        URL.revokeObjectURL(preview.url);
      }
      const { blob } = await fetchDocumentBlob(doc.id);
      const url = URL.createObjectURL(blob);
      let text: string | undefined;
      if (
        doc.content_type.startsWith("text/") ||
        doc.filename.toLowerCase().endsWith(".md") ||
        doc.filename.toLowerCase().endsWith(".txt")
      ) {
        text = await blob.text();
      }
      setPreview({
        url,
        filename: doc.filename,
        contentType: doc.content_type || blob.type || "application/octet-stream",
        text,
      });
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewBusy(false);
    }
  }

  function closePreview() {
    if (preview?.url) {
      URL.revokeObjectURL(preview.url);
    }
    setPreview(null);
  }

  return (
    <div className="chat-docs">
      <div className="chat-docs-head">
        <span className="chat-docs-label">Documents</span>
        <button
          type="button"
          className="linkish"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
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
      <Explainer summary="What happens on upload">{DOC_UPLOAD}</Explainer>
      {previewError ? <p className="form-error">{previewError}</p> : null}
      {documents.length === 0 ? (
        <p className="muted compact-muted">No files in this chat yet.</p>
      ) : (
        <ul className="doc-list nested">
          {documents.map((doc) => (
            <li key={doc.id}>
              <div className="doc-meta">
                <strong title={doc.filename}>{doc.filename}</strong>
                <span className={`status ${doc.status}`}>{doc.status}</span>
              </div>
              <div className="doc-actions">
                <button
                  type="button"
                  className="linkish"
                  disabled={busy || previewBusy}
                  onClick={() => handlePreview(doc)}
                >
                  Preview
                </button>
                <button
                  type="button"
                  className="linkish danger"
                  disabled={busy}
                  onClick={() => onDelete(doc.id)}
                >
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {preview ? (
        <div className="preview-overlay" role="dialog" aria-modal="true" aria-label="Document preview">
          <div className="preview-modal">
            <div className="preview-head">
              <strong>{preview.filename}</strong>
              <button type="button" className="ghost" onClick={closePreview}>
                Close
              </button>
            </div>
            {preview.text != null ? (
              <pre className="preview-text">{preview.text}</pre>
            ) : (
              <iframe title={preview.filename} src={preview.url} className="preview-frame" />
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
