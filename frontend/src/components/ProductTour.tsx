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

    function measure() {
      const element = document.querySelector<HTMLElement>(step.target || "");
      if (!element) {
        setTargetRect(null);
        return;
      }
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
    };
  }, [active, step]);

  const cardStyle = useMemo(() => {
    if (!targetRect || isIntro) {
      return undefined;
    }

    const gap = 16;
    const cardWidth = Math.min(360, window.innerWidth - 32);
    const prefersRight = targetRect.left + targetRect.width + cardWidth + gap < window.innerWidth;
    const left = prefersRight
      ? targetRect.left + targetRect.width + gap
      : Math.max(16, Math.min(targetRect.left, window.innerWidth - cardWidth - 16));
    const top = Math.max(16, Math.min(targetRect.top, window.innerHeight - 260));

    return {
      left,
      top,
      width: cardWidth,
    };
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
      <div className="tour-scrim" />
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

function Spotlight({ rect }: { rect: Rect }) {
  const pad = 8;
  return (
    <div
      className="tour-spotlight"
      style={{
        top: rect.top - pad,
        left: rect.left - pad,
        width: rect.width + pad * 2,
        height: rect.height + pad * 2,
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
        x
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
