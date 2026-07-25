import { LiveBusyStep } from "./BusyStatus";

type Props = {
  steps: LiveBusyStep[];
  open: boolean;
  onToggle: () => void;
};

function stepLine(step: LiveBusyStep): string {
  return step.detail ? `${step.title}  ${step.detail}` : step.title;
}

export function ThinkingReplay({ steps, open, onToggle }: Props) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="thinking-replay">
      <button
        type="button"
        className="thinking-replay-toggle linkish"
        title="Operational progress events from the agent, not private chain-of-thought"
        onClick={onToggle}
      >
        {open ? "Hide agent steps ▾" : "Show agent steps ▸"}
      </button>
      {open ? (
        <ul className="busy-steps thinking-replay-list">
          {steps.map((step) => (
            <li key={step.id} className="busy-step is-done">
              <span className="busy-step-mark" aria-hidden="true">
                ✓
              </span>
              <span className="busy-step-body">
                <span className="busy-step-line">{stepLine(step)}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
