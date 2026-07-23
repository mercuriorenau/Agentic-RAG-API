import { useEffect, useRef, useState } from "react";

type Props = {
  text: string;
  active: boolean;
  className?: string;
  as?: "p" | "span";
  /** Characters revealed per tick. */
  charsPerTick?: number;
  /** Interval between ticks in ms. */
  tickMs?: number;
  /** Wait before typing starts (ms). */
  delayMs?: number;
  /** Fired once when the full text has been revealed (active mode only). */
  onComplete?: () => void;
};

export function TypewriterText({
  text,
  active,
  className,
  as = "span",
  charsPerTick = 1,
  tickMs = 18,
  delayMs = 0,
  onComplete,
}: Props) {
  const [shown, setShown] = useState(active ? "" : text);
  const Tag = as;
  const completedFor = useRef<string | null>(null);

  useEffect(() => {
    completedFor.current = null;
    let intervalId: number | null = null;
    let delayId: number | null = null;

    if (!active) {
      setShown(text);
      return;
    }

    setShown("");
    delayId = window.setTimeout(() => {
      let index = 0;
      intervalId = window.setInterval(() => {
        index = Math.min(index + charsPerTick, text.length);
        setShown(text.slice(0, index));
        if (index >= text.length) {
          if (intervalId != null) {
            window.clearInterval(intervalId);
          }
          if (completedFor.current !== text) {
            completedFor.current = text;
            onComplete?.();
          }
        }
      }, tickMs);
    }, delayMs);

    return () => {
      if (delayId != null) {
        window.clearTimeout(delayId);
      }
      if (intervalId != null) {
        window.clearInterval(intervalId);
      }
    };
  }, [active, text, charsPerTick, tickMs, delayMs, onComplete]);

  return (
    <Tag className={className}>
      {shown}
      {active && shown.length < text.length ? (
        <span className="typewriter-caret" aria-hidden="true" />
      ) : null}
    </Tag>
  );
}
