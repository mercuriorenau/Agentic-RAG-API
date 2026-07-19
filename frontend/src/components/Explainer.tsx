import { useEffect, useRef, useState } from "react";

type Props = {
  children?: string;
  /** Prefer this when the note has more than one short paragraph. */
  paragraphs?: string[];
  /** When set, used as the popover title. */
  summary?: string;
  /** Only one note should own the tour spotlight target. */
  tourAnchor?: boolean;
  /** Prefer end when the icon sits on the right side of a header. */
  align?: "start" | "end";
};

export function Explainer({
  children,
  paragraphs,
  summary,
  tourAnchor = false,
  align = "start",
}: Props) {
  const texts = paragraphs ?? (children ? [children] : []);
  return (
    <TechNote
      title={summary || "How this works"}
      paragraphs={texts}
      tourAnchor={tourAnchor}
      align={align}
    />
  );
}

type MultiProps = {
  title: string;
  paragraphs: string[];
  open?: boolean;
  tourAnchor?: boolean;
  align?: "start" | "end";
};

export function AnswerExplainerBlock({
  title,
  paragraphs,
  tourAnchor,
  align,
}: MultiProps) {
  return (
    <TechNote
      title={title}
      paragraphs={paragraphs}
      tourAnchor={tourAnchor}
      align={align}
    />
  );
}

type TechNoteProps = {
  title: string;
  paragraphs: string[];
  tourAnchor?: boolean;
  align?: "start" | "end";
};

function TechNote({
  title,
  paragraphs,
  tourAnchor = false,
  align = "start",
}: TechNoteProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <span
      ref={rootRef}
      className={`tech-note align-${align}`}
      data-tour={tourAnchor ? "tech-note" : undefined}
    >
      <button
        type="button"
        className="tech-note-trigger"
        aria-expanded={open}
        aria-label={title}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="tech-note-ring" aria-hidden="true" />
        <span className="tech-note-copy" aria-hidden="true">
          <span className="tech-note-more">more&nbsp;</span>
          <span className="tech-note-i-slot">
            <span className="tech-note-glyph">i</span>
          </span>
          <span className="tech-note-nfo">nfo</span>
        </span>
      </button>
      {open ? (
        <span className={`tech-note-popover align-${align}`} role="note">
          <strong>{title}</strong>
          {paragraphs.map((paragraph, index) => (
            <span key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</span>
          ))}
        </span>
      ) : null}
    </span>
  );
}
