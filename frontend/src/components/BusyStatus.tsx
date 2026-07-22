import { useEffect, useState } from "react";

type Props = {
  active: boolean;
  label: string;
  phases?: string[];
};

export function BusyStatus({ active, label, phases }: Props) {
  const [phaseIndex, setPhaseIndex] = useState(0);
  const detail =
    phases && phases.length > 0 ? phases[phaseIndex % phases.length] : undefined;

  useEffect(() => {
    if (!active || !phases || phases.length === 0) {
      setPhaseIndex(0);
      return;
    }
    const id = window.setInterval(() => {
      setPhaseIndex((current) => (current + 1) % phases.length);
    }, 2200);
    return () => window.clearInterval(id);
  }, [active, phases]);

  if (!active) {
    return null;
  }

  return (
    <div className="busy-status" role="status" aria-live="polite" aria-busy="true">
      <span className="busy-spinner" aria-hidden="true" />
      <span className="busy-copy">
        <strong>{label}</strong>
        {detail ? <span className="busy-detail">{detail}</span> : null}
      </span>
      <span className="busy-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}

export const ASK_BUSY_PHASES = [
  "Inspecting the question and picking a model…",
  "Deciding retrieve, web, or direct…",
  "Searching uploads and grading evidence…",
  "Writing a grounded answer…",
];

export const UPLOAD_BUSY_PHASES = [
  "Uploading the file…",
  "Extracting text…",
  "Chunking and embedding…",
  "Saving vectors in Postgres…",
];
