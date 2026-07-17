import { ChangeEvent, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
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

  useEffect(() => {
    if (!preview) {
      return;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closePreview();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
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
      const mime =
        doc.content_type ||
        blob.type ||
        (doc.filename.toLowerCase().endsWith(".pdf") ? "application/pdf" : "application/octet-stream");
      const typedBlob = blob.type === mime ? blob : new Blob([await blob.arrayBuffer()], { type: mime });
      const url = URL.createObjectURL(typedBlob);
      let text: string | undefined;
      if (
        mime.startsWith("text/") ||
        doc.filename.toLowerCase().endsWith(".md") ||
        doc.filename.toLowerCase().endsWith(".txt")
      ) {
        text = await typedBlob.text();
      }
      setPreview({
        url,
        filename: doc.filename,
        contentType: mime,
        text,
      });
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewBusy(false);
    }
  }

  function closePreview() {
    setPreview((current) => {
      if (current?.url) {
        URL.revokeObjectURL(current.url);
      }
      return null;
    });
  }

  return (
    <div className="chat-docs">
      <div className="chat-docs-head">
        <span className="chat-docs-label">Documents</span>
        <button
          type="button"
          className="linkish"
          data-tour="upload-doc"
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
                  data-tour="preview-doc"
                  disabled={busy || previewBusy}
                  onClick={() => handlePreview(doc)}
                >
                  Preview
                </button>
                <button
                  type="button"
                  className="linkish danger"
                  data-tour="remove-doc"
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

      {preview
        ? createPortal(
            <div
              className="preview-overlay"
              role="dialog"
              aria-modal="true"
              aria-label={`Preview ${preview.filename}`}
              onClick={closePreview}
            >
              <button
                type="button"
                className="preview-close"
                aria-label="Close preview"
                onClick={(event) => {
                  event.stopPropagation();
                  closePreview();
                }}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path
                    d="M6.2 6.2a1.1 1.1 0 0 1 1.55 0L12 10.45l4.25-4.25a1.1 1.1 0 1 1 1.55 1.55L13.55 12l4.25 4.25a1.1 1.1 0 1 1-1.55 1.55L12 13.55l-4.25 4.25a1.1 1.1 0 1 1-1.55-1.55L10.45 12 6.2 7.75a1.1 1.1 0 0 1 0-1.55Z"
                    fill="currentColor"
                  />
                </svg>
              </button>
              <div className="preview-modal" onClick={(event) => event.stopPropagation()}>
                {preview.text != null ? (
                  <pre className="preview-text">{preview.text}</pre>
                ) : (
                  <iframe title={preview.filename} src={preview.url} className="preview-frame" />
                )}
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
