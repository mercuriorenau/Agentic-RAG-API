import type { CSSProperties } from "react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { TOUR_INVITE, TOUR_STEPS, TourStep } from "../tour/tourSteps";

export type TourMode = "invite" | "guide";

type Props = {
  active: boolean;
  mode: TourMode;
  onClose: () => void;
  onComplete: () => void;
  onAcceptInvite: () => void;
  onDeclineInvite: () => void;
};

type Rect = {
  top: number;
  left: number;
  width: number;
  height: number;
};

const SPOTLIGHT_RADIUS_MAX = 14;
/** Clear of the ring, without pushing the card far away. */
const CARD_GAP = 18;

/** Tight pad on small controls (info i); roomier pad on wide targets (answers). */
function spotlightPad(rect: Rect): number {
  const size = Math.min(rect.width, rect.height);
  if (size <= 36) {
    return 5;
  }
  if (size <= 72) {
    return 10;
  }
  return 16;
}

function spotlightRadius(rect: Rect, pad: number): number {
  const box = Math.min(rect.width, rect.height) + pad * 2;
  return Math.min(SPOTLIGHT_RADIUS_MAX, Math.max(8, box / 3));
}

export function ProductTour({
  active,
  mode,
  onClose,
  onComplete,
  onAcceptInvite,
  onDeclineInvite,
}: Props) {
  const [index, setIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<Rect | null>(null);
  const [spaceHintFlown, setSpaceHintFlown] = useState(false);
  const step = TOUR_STEPS[index];
  const isInvite = mode === "invite";
  const isCentered = isInvite || !step?.target;
  const isTechNoteStep = Boolean(step?.target?.includes("tech-note"));

  const nextStep = useCallback(() => {
    if (index >= TOUR_STEPS.length - 1) {
      onComplete();
      return;
    }
    setIndex((current) => current + 1);
  }, [index, onComplete]);

  const previousStep = useCallback(() => {
    setIndex((current) => Math.max(0, current - 1));
  }, []);

  useEffect(() => {
    if (active && mode === "guide") {
      setIndex(0);
    }
  }, [active, mode]);

  useEffect(() => {
    if (!active) {
      setSpaceHintFlown(false);
    }
  }, [active]);

  useEffect(() => {
    if (!active) {
      return;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== " " && event.code !== "Space") {
        return;
      }
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable) {
        return;
      }
      event.preventDefault();
      if (isInvite) {
        onAcceptInvite();
        return;
      }
      nextStep();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [active, isInvite, nextStep, onAcceptInvite]);

  useLayoutEffect(() => {
    if (!active || isInvite || !step?.target) {
      setTargetRect(null);
      return;
    }

    let currentTarget: HTMLElement | null = null;

    function measure() {
      const element = document.querySelector<HTMLElement>(step.target || "");
      if (currentTarget && currentTarget !== element) {
        currentTarget.classList.remove("tour-target-active");
      }
      currentTarget = element;
      if (!element) {
        setTargetRect(null);
        return;
      }
      element.classList.add("tour-target-active");
      const rect = element.getBoundingClientRect();
      setTargetRect({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      });
    }

    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
      currentTarget?.classList.remove("tour-target-active");
    };
  }, [active, isInvite, step]);

  const cardStyle = useMemo(() => {
    if (!targetRect || isCentered) {
      return undefined;
    }

    const edge = 28;
    const pad = spotlightPad(targetRect);
    const gap = CARD_GAP + pad;
    const minWidth = 260;
    const preferredWidth = Math.min(340, window.innerWidth - edge * 2);
    const spotlightLeft = targetRect.left - pad;
    const spotlightRight = targetRect.left + targetRect.width + pad;
    const rightMargin = Math.max(edge, window.innerWidth - spotlightRight);

    const spaceRight = window.innerWidth - spotlightRight - gap - edge;
    const spaceLeft = spotlightLeft - gap - edge;

    let left: number;
    let width = preferredWidth;

    if (spaceRight >= preferredWidth) {
      left = targetRect.left + targetRect.width + gap;
      const maxRight = window.innerWidth - rightMargin;
      if (left + width > maxRight) {
        width = Math.max(minWidth, maxRight - left);
      }
    } else if (spaceLeft >= minWidth) {
      const cardRight = targetRect.left - gap;
      left = cardRight - preferredWidth;
      const desiredLeft = Math.max(edge, rightMargin);
      if (left < desiredLeft) {
        left = desiredLeft;
        width = Math.max(minWidth, cardRight - left);
      }
      if (left < edge) {
        left = edge;
        width = Math.max(minWidth, cardRight - left);
      }
    } else {
      left = Math.max(edge, Math.min(targetRect.left, window.innerWidth - preferredWidth - edge));
      width = preferredWidth;
    }

    const preferBelow = targetRect.top < 120 || (spaceRight < minWidth && spaceLeft < minWidth);
    const top = preferBelow
      ? Math.min(targetRect.top + targetRect.height + gap, window.innerHeight - 240)
      : Math.max(edge, Math.min(targetRect.top - 8, window.innerHeight - 240));

    return {
      left,
      top: Math.max(edge, top),
      width,
    };
  }, [isCentered, targetRect]);

  const scrimStyle = useMemo(() => {
    if (!targetRect || isCentered) {
      return undefined;
    }
    const pad = spotlightPad(targetRect);
    if (isTechNoteStep) {
      return { clipPath: holeClipPathCircle(targetRect, pad) };
    }
    return { clipPath: holeClipPath(targetRect, pad, spotlightRadius(targetRect, pad)) };
  }, [isCentered, isTechNoteStep, targetRect]);

  if (!active) {
    return null;
  }

  if (isInvite) {
    return (
      <div className="tour-layer" role="dialog" aria-modal="true" aria-label="Project guide invite">
        <div className="tour-scrim" />
        <section className="tour-card tour-card-intro">
          <button type="button" className="tour-close" aria-label="Close" onClick={onDeclineInvite}>
            ×
          </button>
          <span className="tour-kicker">First visit</span>
          <h2>{TOUR_INVITE.title}</h2>
          <p>{TOUR_INVITE.body}</p>
          <div className="tour-actions">
            <button type="button" className="ghost" onClick={onDeclineInvite}>
              {TOUR_INVITE.declineLabel}
            </button>
            <button type="button" data-tour-next onClick={onAcceptInvite}>
              {TOUR_INVITE.acceptLabel}
            </button>
          </div>
        </section>
        <SpaceHint flown={spaceHintFlown} onFlown={() => setSpaceHintFlown(true)} />
      </div>
    );
  }

  if (!step) {
    return null;
  }

  return (
    <div className="tour-layer" role="dialog" aria-modal="true" aria-label="Product tour">
      <div className="tour-scrim" style={scrimStyle} />
      {targetRect && !isCentered ? (
        <Spotlight rect={targetRect} circular={isTechNoteStep} />
      ) : null}
      <TourCard
        step={step}
        index={index}
        total={TOUR_STEPS.length}
        isCentered={isCentered}
        style={cardStyle}
        onClose={onClose}
        onNext={nextStep}
        onPrevious={previousStep}
      />
      <SpaceHint flown={spaceHintFlown} onFlown={() => setSpaceHintFlown(true)} />
    </div>
  );
}

function holeClipPathCircle(rect: Rect, pad: number): string {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const radius = Math.max(rect.width, rect.height) / 2 + pad;
  const outer = `M0 0 H${vw} V${vh} H0 Z`;
  const hole = [
    `M${cx - radius} ${cy}`,
    `A${radius} ${radius} 0 1 0 ${cx + radius} ${cy}`,
    `A${radius} ${radius} 0 1 0 ${cx - radius} ${cy}`,
    "Z",
  ].join(" ");
  return `path(evenodd, "${outer} ${hole}")`;
}

function holeClipPath(rect: Rect, pad: number, radius: number): string {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const top = Math.max(0, rect.top - pad);
  const left = Math.max(0, rect.left - pad);
  const right = Math.min(vw, rect.left + rect.width + pad);
  const bottom = Math.min(vh, rect.top + rect.height + pad);
  const r = Math.min(radius, (right - left) / 2, (bottom - top) / 2);

  const outer = `M0 0 H${vw} V${vh} H0 Z`;
  const hole = [
    `M${left + r} ${top}`,
    `H${right - r}`,
    `A${r} ${r} 0 0 1 ${right} ${top + r}`,
    `V${bottom - r}`,
    `A${r} ${r} 0 0 1 ${right - r} ${bottom}`,
    `H${left + r}`,
    `A${r} ${r} 0 0 1 ${left} ${bottom - r}`,
    `V${top + r}`,
    `A${r} ${r} 0 0 1 ${left + r} ${top}`,
    "Z",
  ].join(" ");

  return `path(evenodd, "${outer} ${hole}")`;
}

function Spotlight({ rect, circular = false }: { rect: Rect; circular?: boolean }) {
  const pad = spotlightPad(rect);
  if (circular) {
    const side = Math.max(rect.width, rect.height) + pad * 2;
    return (
      <div
        className="tour-spotlight tour-spotlight-circle"
        style={{
          top: rect.top + rect.height / 2 - side / 2,
          left: rect.left + rect.width / 2 - side / 2,
          width: side,
          height: side,
        }}
      />
    );
  }
  return (
    <div
      className="tour-spotlight"
      style={{
        top: rect.top - pad,
        left: rect.left - pad,
        width: rect.width + pad * 2,
        height: rect.height + pad * 2,
        borderRadius: spotlightRadius(rect, pad),
      }}
    />
  );
}

function SpaceHint({ flown, onFlown }: { flown: boolean; onFlown: () => void }) {
  const [delta, setDelta] = useState<{ dx: number; dy: number } | null>(null);

  useLayoutEffect(() => {
    if (flown) {
      setDelta({ dx: 0, dy: 0 });
      return;
    }
    const button = document.querySelector<HTMLElement>("[data-tour-next]");
    if (!button) {
      setDelta({ dx: 0, dy: 0 });
      return;
    }
    const rect = button.getBoundingClientRect();
    const fromX = rect.left + rect.width / 2;
    const fromY = rect.top + rect.height / 2;
    const toX = window.innerWidth / 2;
    const toY = window.innerHeight - 28;
    setDelta({ dx: fromX - toX, dy: fromY - toY });
  }, [flown]);

  if (!delta) {
    return null;
  }

  return (
    <p
      className={flown ? "tour-space-hint is-settled" : "tour-space-hint"}
      style={
        flown
          ? undefined
          : ({
              "--hint-dx": `${delta.dx}px`,
              "--hint-dy": `${delta.dy}px`,
            } as CSSProperties)
      }
      onAnimationEnd={() => onFlown()}
    >
      Space to continue
    </p>
  );
}

type CardProps = {
  step: TourStep;
  index: number;
  total: number;
  isCentered: boolean;
  style?: CSSProperties;
  onClose: () => void;
  onNext: () => void;
  onPrevious: () => void;
};

function TourCard({
  step,
  index,
  total,
  isCentered,
  style,
  onClose,
  onNext,
  onPrevious,
}: CardProps) {
  const className = isCentered || !style ? "tour-card tour-card-intro" : "tour-card";

  return (
    <section className={className} style={style}>
      <button type="button" className="tour-close" aria-label="Close tour" onClick={onClose}>
        ×
      </button>
      <span className="tour-kicker">
        {isCentered ? "Guide" : `Step ${index + 1} of ${total}`}
      </span>
      <h2>{step.title}</h2>
      <p>{step.body}</p>
      <div className="tour-actions">
        <button type="button" className="ghost" disabled={index === 0} onClick={onPrevious}>
          Back
        </button>
        <button type="button" data-tour-next onClick={onNext}>
          {index === total - 1 ? "Finish" : "Next"}
        </button>
      </div>
    </section>
  );
}
