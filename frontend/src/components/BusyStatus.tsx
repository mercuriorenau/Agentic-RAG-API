import { useEffect, useRef, useState } from "react";
import { TypewriterText } from "./TypewriterText";

export type BusyPhase = {
  title: string;
  detail: string;
};

export type LiveBusyStep = {
  id: string;
  title: string;
  detail?: string;
};

type Props = {
  active: boolean;
  label: string;
  /** Real-time agent steps (Ask). Takes priority over simulated phases. */
  liveSteps?: LiveBusyStep[];
  /** Simulated phases (Upload) when liveSteps is empty. */
  phases?: BusyPhase[];
  storageKey?: string;
  className?: string;
  /** Called when every queued live step has finished typing. */
  onCaughtUp?: () => void;
};

const THINK_TICK_MS = 28;
const THINK_CHARS = 1;
const MIN_STEP_HOLD_MS = 320;

function loadExpanded(storageKey: string | undefined, fallback: boolean): boolean {
  if (!storageKey || typeof window === "undefined") {
    return fallback;
  }
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (raw === "1") {
      return true;
    }
    if (raw === "0") {
      return false;
    }
  } catch {
    /* ignore */
  }
  return fallback;
}

function stepLine(step: LiveBusyStep): string {
  return step.detail ? `${step.title}  ${step.detail}` : step.title;
}

export function BusyStatus({
  active,
  label,
  liveSteps = [],
  phases = [],
  storageKey,
  className,
  onCaughtUp,
}: Props) {
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [expanded, setExpanded] = useState(() => loadExpanded(storageKey, true));
  /** How many live steps are fully revealed (done). */
  const [revealedCount, setRevealedCount] = useState(0);
  /** Index currently typing, or -1 if idle between steps. */
  const [typingIndex, setTypingIndex] = useState(-1);
  const usingLive = liveSteps.length > 0;
  const holdTimer = useRef<number | null>(null);
  const caughtUpFor = useRef(0);
  const finishLock = useRef(false);

  useEffect(() => {
    finishLock.current = false;
  }, [typingIndex]);

  useEffect(() => {
    if (!active) {
      setPhaseIndex(0);
      setRevealedCount(0);
      setTypingIndex(-1);
      caughtUpFor.current = 0;
      finishLock.current = false;
      if (holdTimer.current != null) {
        window.clearTimeout(holdTimer.current);
        holdTimer.current = null;
      }
      return;
    }
    if (usingLive) {
      return;
    }
    if (phases.length === 0) {
      setPhaseIndex(0);
      return;
    }
    setPhaseIndex(0);
    const id = window.setInterval(() => {
      setPhaseIndex((current) => Math.min(current + 1, phases.length - 1));
    }, 2400);
    return () => window.clearInterval(id);
  }, [active, phases, usingLive]);

  // Queue: start typing the next live step when idle and more steps exist.
  useEffect(() => {
    if (!active || !usingLive) {
      return;
    }
    if (typingIndex >= 0) {
      return;
    }
    if (revealedCount < liveSteps.length) {
      setTypingIndex(revealedCount);
    }
  }, [active, usingLive, liveSteps.length, revealedCount, typingIndex]);

  // Notify parent when every queued step has finished typing.
  useEffect(() => {
    if (!active || !usingLive || !onCaughtUp) {
      return;
    }
    if (typingIndex >= 0) {
      return;
    }
    if (liveSteps.length === 0) {
      return;
    }
    if (revealedCount >= liveSteps.length && caughtUpFor.current !== liveSteps.length) {
      caughtUpFor.current = liveSteps.length;
      onCaughtUp();
    }
  }, [active, usingLive, liveSteps.length, revealedCount, typingIndex, onCaughtUp]);

  function finishCurrentStep() {
    if (finishLock.current) {
      return;
    }
    finishLock.current = true;
    if (holdTimer.current != null) {
      window.clearTimeout(holdTimer.current);
    }
    holdTimer.current = window.setTimeout(() => {
      holdTimer.current = null;
      setRevealedCount((count) => count + 1);
      setTypingIndex(-1);
    }, MIN_STEP_HOLD_MS);
  }

  function setExpandedPersist(next: boolean) {
    setExpanded(next);
    if (storageKey) {
      try {
        window.sessionStorage.setItem(storageKey, next ? "1" : "0");
      } catch {
        /* ignore */
      }
    }
  }

  if (!active) {
    return null;
  }

  const displaySteps: LiveBusyStep[] = usingLive
    ? liveSteps.slice(0, Math.max(revealedCount, typingIndex >= 0 ? typingIndex + 1 : 0))
    : phases.slice(0, phaseIndex + 1).map((phase, index) => ({
        id: `phase-${index}`,
        title: phase.title,
        detail: phase.detail,
      }));

  const latest = displaySteps[displaySteps.length - 1];
  const summary = latest ? stepLine(latest) : "Working…";
  const summaryTyping = usingLive && typingIndex >= 0;

  return (
    <div
      className={["busy-status", className].filter(Boolean).join(" ")}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <button
        type="button"
        className="busy-status-head"
        aria-expanded={expanded}
        aria-controls={displaySteps.length ? "busy-steps-panel" : undefined}
        onClick={() => setExpandedPersist(!expanded)}
      >
        <span className="busy-spinner" aria-hidden="true" />
        <span className="busy-copy">
          <strong>{label}</strong>
          {!expanded ? (
            <TypewriterText
              key={latest?.id || "idle"}
              className="busy-detail"
              text={summary}
              active={summaryTyping || !usingLive}
              charsPerTick={THINK_CHARS}
              tickMs={THINK_TICK_MS}
              onComplete={
                usingLive && typingIndex >= 0 ? finishCurrentStep : undefined
              }
            />
          ) : null}
        </span>
        {displaySteps.length > 0 ? (
          <span className="busy-toggle-label" aria-hidden="true">
            {expanded ? "Hide ▾" : "Show ▸"}
          </span>
        ) : null}
      </button>

      {expanded && displaySteps.length > 0 ? (
        <ul id="busy-steps-panel" className="busy-steps">
          {displaySteps.map((step, index) => {
            const isActive = usingLive
              ? index === typingIndex
              : index === displaySteps.length - 1;
            const line = stepLine(step);
            return (
              <li
                key={step.id}
                className={isActive ? "busy-step is-active" : "busy-step is-done"}
              >
                <span className="busy-step-mark" aria-hidden="true">
                  {isActive ? "›" : "✓"}
                </span>
                <span className="busy-step-body">
                  {isActive ? (
                    <TypewriterText
                      key={step.id}
                      className="busy-step-line"
                      text={line}
                      active
                      charsPerTick={THINK_CHARS}
                      tickMs={THINK_TICK_MS}
                      onComplete={usingLive ? finishCurrentStep : undefined}
                    />
                  ) : (
                    <span className="busy-step-line">{line}</span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

export const UPLOAD_BUSY_PHASES: BusyPhase[] = [
  {
    title: "Upload the file",
    detail: "Sending the PDF/TXT/Markdown into this chat’s private store.",
  },
  {
    title: "Extract text",
    detail: "Page-aware extraction pulls readable text from the file.",
  },
  {
    title: "Chunk and embed",
    detail: "Paragraph windows are embedded with text-embedding-3-small.",
  },
  {
    title: "Save vectors in Postgres",
    detail: "Chunks land in pgvector under this chat only.",
  },
];
