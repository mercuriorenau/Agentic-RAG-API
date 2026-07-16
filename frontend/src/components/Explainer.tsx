type Props = {
  children: string;
  /** When set, render as a collapsible block with this summary label. */
  summary?: string;
  open?: boolean;
};

export function Explainer({ children, summary, open = false }: Props) {
  if (summary) {
    return (
      <details className="explainer" open={open}>
        <summary>{summary}</summary>
        <p>{children}</p>
      </details>
    );
  }

  return <p className="explainer-inline">{children}</p>;
}

type MultiProps = {
  title: string;
  paragraphs: string[];
  open?: boolean;
};

export function AnswerExplainerBlock({ title, paragraphs, open = false }: MultiProps) {
  return (
    <details className="explainer" open={open}>
      <summary>{title}</summary>
      {paragraphs.map((paragraph, index) => (
        <p key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</p>
      ))}
    </details>
  );
}
