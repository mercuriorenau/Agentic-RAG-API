import type { CSSProperties } from "react";
import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { TOUR_STEPS, TourStep } from "../tour/tourSteps";

type Props = {
  active: boolean;
  onClose: () => void;
  onComplete: () => void;
};

type Rect = {
  top: number;
  left: number;
  width: number;
  height: number;
};

const SPOTLIGHT_PAD = 10;
const SPOTLIGHT_RADIUS = 14;

export function ProductTour({ active, onClose, onComplete }: Props) {
  const [index, setIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<Rect | null>(null);
  const step = TOUR_STEPS[index];
  const isIntro = !step?.target;

  useEffect(() => {
    if (active) {
      setIndex(0);
    }
  }, [active]);

  useLayoutEffect(() => {
    if (!active || !step?.target) {
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
  }, [active, step]);

  const cardStyle = useMemo(() => {
    if (!targetRect || isIntro) {
      return undefined;
    }

    const gap = 16;
    const cardWidth = Math.min(360, window.innerWidth - 32);
    const spaceRight = window.innerWidth - (targetRect.left + targetRect.width + gap);
    const spaceLeft = targetRect.left - gap;
    let left: number;
    if (spaceRight >= cardWidth) {
      left = targetRect.left + targetRect.width + gap;
    } else if (spaceLeft >= cardWidth) {
      left = targetRect.left - cardWidth - gap;
    } else {
      left = Math.max(16, Math.min(targetRect.left, window.innerWidth - cardWidth - 16));
    }

    const preferBelow = targetRect.top < 120;
    const top = preferBelow
      ? Math.min(targetRect.top + targetRect.height + gap, window.innerHeight - 260)
      : Math.max(16, Math.min(targetRect.top, window.innerHeight - 260));

    return {
      left,
      top: Math.max(16, top),
      width: cardWidth,
    };
  }, [isIntro, targetRect]);

  const scrimStyle = useMemo(() => {
    if (!targetRect || isIntro) {
      return undefined;
    }
    return { clipPath: holeClipPath(targetRect, SPOTLIGHT_PAD) };
  }, [isIntro, targetRect]);

  if (!active || !step) {
    return null;
  }

  function closeTour() {
    onClose();
  }

  function nextStep() {
    if (index >= TOUR_STEPS.length - 1) {
      onComplete();
      return;
    }
    setIndex((current) => current + 1);
  }

  function previousStep() {
    setIndex((current) => Math.max(0, current - 1));
  }

  return (
    <div className="tour-layer" role="dialog" aria-modal="true" aria-label="Product tour">
      <div className="tour-scrim" style={scrimStyle} />
      {targetRect && !isIntro ? <Spotlight rect={targetRect} /> : null}
      <TourCard
        step={step}
        index={index}
        total={TOUR_STEPS.length}
        isIntro={isIntro}
        style={cardStyle}
        onClose={closeTour}
        onNext={nextStep}
        onPrevious={previousStep}
      />
    </div>
  );
}

function holeClipPath(rect: Rect, pad: number): string {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const top = Math.max(0, rect.top - pad);
  const left = Math.max(0, rect.left - pad);
  const right = Math.min(vw, rect.left + rect.width + pad);
  const bottom = Math.min(vh, rect.top + rect.height + pad);
  const r = Math.min(SPOTLIGHT_RADIUS, (right - left) / 2, (bottom - top) / 2);

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

function Spotlight({ rect }: { rect: Rect }) {
  return (
    <div
      className="tour-spotlight"
      style={{
        top: rect.top - SPOTLIGHT_PAD,
        left: rect.left - SPOTLIGHT_PAD,
        width: rect.width + SPOTLIGHT_PAD * 2,
        height: rect.height + SPOTLIGHT_PAD * 2,
      }}
    />
  );
}

type CardProps = {
  step: TourStep;
  index: number;
  total: number;
  isIntro: boolean;
  style?: CSSProperties;
  onClose: () => void;
  onNext: () => void;
  onPrevious: () => void;
};

function TourCard({
  step,
  index,
  total,
  isIntro,
  style,
  onClose,
  onNext,
  onPrevious,
}: CardProps) {
  const className = isIntro || !style ? "tour-card tour-card-intro" : "tour-card";

  return (
    <section className={className} style={style}>
      <button type="button" className="tour-close" aria-label="Close tour" onClick={onClose}>
        ×
      </button>
      <span className="tour-kicker">{isIntro ? "Start here" : `Step ${index + 1} of ${total}`}</span>
      <h2>{step.title}</h2>
      <p>{step.body}</p>
      <div className="tour-actions">
        <button type="button" className="ghost" disabled={index === 0} onClick={onPrevious}>
          Back
        </button>
        <button type="button" onClick={onNext}>
          {index === total - 1 ? "Finish" : "Next"}
        </button>
      </div>
    </section>
  );
}
