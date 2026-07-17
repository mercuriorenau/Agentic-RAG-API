import { useState } from "react";

type Props = {
  children: string;
  /** When set, render as a collapsible block with this summary label. */
  summary?: string;
  open?: boolean;
};

export function Explainer({ children, summary }: Props) {
  return <TechNote title={summary || "How this works"} paragraphs={[children]} />;
}

type MultiProps = {
  title: string;
  paragraphs: string[];
  open?: boolean;
};

export function AnswerExplainerBlock({ title, paragraphs }: MultiProps) {
  return <TechNote title={title} paragraphs={paragraphs} />;
}

type TechNoteProps = {
  title: string;
  paragraphs: string[];
};

function TechNote({ title, paragraphs }: TechNoteProps) {
  const [open, setOpen] = useState(false);

  return (
    <span className="tech-note">
      <button
        type="button"
        className="tech-note-trigger"
        aria-expanded={open}
        aria-label={title}
        onClick={() => setOpen((current) => !current)}
      >
        i
      </button>
      {open ? (
        <span className="tech-note-popover" role="note">
          <strong>{title}</strong>
          {paragraphs.map((paragraph, index) => (
            <span key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</span>
          ))}
        </span>
      ) : null}
    </span>
  );
}
