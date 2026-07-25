const STACK_ITEMS = [
  { name: "OpenAI", icon: "chat" },
  { name: "Claude", icon: "ai" },
  { name: "Tavily", icon: "search" },
  { name: "Railway", icon: "deploy" },
  { name: "PostgreSQL", icon: "database" },
  { name: "pgvector", icon: "vectordb" },
  { name: "SQLAlchemy", icon: "orm" },
  { name: "Alembic", icon: "migrate" },
  { name: "FastAPI", icon: "api" },
  { name: "React", icon: "ui" },
  { name: "TypeScript", icon: "language" },
  { name: "Vite", icon: "build" },
  { name: "Google Auth", icon: "auth" },
  { name: "Brevo", icon: "mail" },
  { name: "SlowAPI", icon: "api" },
  { name: "Docker", icon: "container" },
] as const;

type IconKind = (typeof STACK_ITEMS)[number]["icon"];

/** Generic category icons, not brand logos. */
function SemanticIcon({ kind }: { kind: IconKind }) {
  const props = {
    viewBox: "0 0 24 24",
    width: 16,
    height: 16,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };

  switch (kind) {
    case "ai":
      return (
        <svg {...props}>
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
          <circle cx="12" cy="12" r="4.2" />
          <path d="M8.2 8.2 6.5 6.5M15.8 8.2 17.5 6.5M8.2 15.8 6.5 17.5M15.8 15.8 17.5 17.5" />
        </svg>
      );
    case "chat":
      return (
        <svg {...props}>
          <path d="M5 6.5h14a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 19 16.5H10l-4 3v-3H5A1.5 1.5 0 0 1 3.5 15V8A1.5 1.5 0 0 1 5 6.5z" />
          <path d="M8 11h.01M12 11h.01M16 11h.01" />
        </svg>
      );
    case "search":
      return (
        <svg {...props}>
          <circle cx="10.5" cy="10.5" r="5.5" />
          <path d="M15 15l5 5" />
        </svg>
      );
    case "deploy":
      return (
        <svg {...props}>
          <path d="M12 3 19 14H5L12 3z" />
          <path d="M12 14v7M9 18h6" />
        </svg>
      );
    case "database":
      return (
        <svg {...props}>
          <ellipse cx="12" cy="6" rx="7" ry="3" />
          <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
          <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
        </svg>
      );
    case "vectordb":
      return (
        <svg {...props}>
          <ellipse cx="12" cy="6.5" rx="6.5" ry="2.6" />
          <path d="M5.5 6.5v5.5c0 1.4 2.9 2.6 6.5 2.6s6.5-1.2 6.5-2.6V6.5" />
          <path d="M5.5 12v5c0 1.4 2.9 2.6 6.5 2.6s6.5-1.2 6.5-2.6v-5" />
          <circle cx="10" cy="12" r="1.1" fill="currentColor" stroke="none" />
          <circle cx="14" cy="14.2" r="1.1" fill="currentColor" stroke="none" />
          <circle cx="12.5" cy="10.2" r="1.1" fill="currentColor" stroke="none" />
        </svg>
      );
    case "orm":
      return (
        <svg {...props}>
          <rect x="4" y="5" width="7" height="6" rx="1" />
          <rect x="13" y="5" width="7" height="6" rx="1" />
          <rect x="8.5" y="13" width="7" height="6" rx="1" />
          <path d="M7.5 11v1.2M16.5 11v1.2M12 11.5v1.5" />
        </svg>
      );
    case "migrate":
      return (
        <svg {...props}>
          <path d="M7 5v14M17 5v14" />
          <path d="M4 8h6M14 16h6" />
          <path d="M7 12h10" />
          <path d="M14 9l3 3-3 3" />
        </svg>
      );
    case "api":
      return (
        <svg {...props}>
          <path d="M8 7H5.5A1.5 1.5 0 0 0 4 8.5v7A1.5 1.5 0 0 0 5.5 17H8" />
          <path d="M16 7h2.5A1.5 1.5 0 0 1 20 8.5v7a1.5 1.5 0 0 1-1.5 1.5H16" />
          <path d="M9 12h6M11 9l-2 3 2 3M13 9l2 3-2 3" />
        </svg>
      );
    case "ui":
      return (
        <svg {...props}>
          <rect x="4" y="5" width="16" height="14" rx="2" />
          <path d="M4 9h16M8 5v4" />
          <rect x="7" y="12" width="4" height="4" rx="0.6" />
          <path d="M13 13h4M13 16h3" />
        </svg>
      );
    case "language":
      return (
        <svg {...props}>
          <path d="M4 6h9M8.5 6v12" />
          <path d="M14 18l3.2-8.5L20.4 18" />
          <path d="M15.1 15h4.2" />
        </svg>
      );
    case "build":
      return (
        <svg {...props}>
          <path d="M5 19V9l7-5 7 5v10" />
          <path d="M10 19v-5h4v5" />
          <path d="M5 11.5h14" />
        </svg>
      );
    case "auth":
      return (
        <svg {...props}>
          <rect x="6" y="11" width="12" height="9" rx="1.5" />
          <path d="M9 11V8a3 3 0 0 1 6 0v3" />
          <circle cx="12" cy="15.5" r="1.2" />
        </svg>
      );
    case "mail":
      return (
        <svg {...props}>
          <rect x="3.5" y="6" width="17" height="12" rx="1.5" />
          <path d="M4.5 7.5 12 13l7.5-5.5" />
        </svg>
      );
    case "container":
      return (
        <svg {...props}>
          <rect x="3.5" y="7" width="17" height="10" rx="1.5" />
          <path d="M3.5 11h17M8 7v10M12 7v10M16 7v10" />
        </svg>
      );
  }
}

export function StackStrip() {
  const items = [...STACK_ITEMS, ...STACK_ITEMS];

  return (
    <aside className="stack-strip" aria-label="Technologies used in this demo">
      <p className="stack-strip-label">Built with</p>
      <div className="stack-marquee">
        <ul className="stack-marquee-track">
          {items.map((item, index) => (
            <li key={`${item.name}-${index}`} className="stack-strip-item">
              <span className="stack-strip-icon" aria-hidden="true">
                <SemanticIcon kind={item.icon} />
              </span>
              <span className="stack-strip-name">{item.name}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="stack-strip-note muted">
        Tools used in this demo. Not affiliated with or endorsed by these companies.
      </p>
    </aside>
  );
}
