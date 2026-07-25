import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { LEGAL_INTRO, LEGAL_SECTIONS, LEGAL_TITLE } from "../legal";

export function LegalNotice() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <>
      <button type="button" className="legal-trigger" onClick={() => setOpen(true)}>
        {LEGAL_TITLE}
      </button>
      {open
        ? createPortal(
            <div
              className="legal-overlay"
              role="dialog"
              aria-modal="true"
              aria-label={LEGAL_TITLE}
              onClick={() => setOpen(false)}
            >
              <div className="legal-modal" onClick={(event) => event.stopPropagation()}>
                <div className="legal-modal-head">
                  <h2>{LEGAL_TITLE}</h2>
                  <button
                    type="button"
                    className="legal-close"
                    aria-label="Close privacy and terms"
                    onClick={() => setOpen(false)}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path
                        d="M6.2 6.2a1.1 1.1 0 0 1 1.55 0L12 10.45l4.25-4.25a1.1 1.1 0 1 1 1.55 1.55L13.55 12l4.25 4.25a1.1 1.1 0 1 1-1.55 1.55L12 13.55l-4.25 4.25a1.1 1.1 0 1 1-1.55-1.55L10.45 12 6.2 7.75a1.1 1.1 0 0 1 0-1.55Z"
                        fill="currentColor"
                      />
                    </svg>
                  </button>
                </div>
                <div className="legal-modal-body">
                  <p className="legal-intro">{LEGAL_INTRO}</p>
                  {LEGAL_SECTIONS.map((section) => (
                    <section key={section.heading} className="legal-section">
                      <h3>{section.heading}</h3>
                      {section.paragraphs.map((paragraph, index) => (
                        <p key={`${section.heading}-${index}`}>{paragraph}</p>
                      ))}
                    </section>
                  ))}
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
