const STORAGE_KEY = "rag_query_lock_until";
const LOCK_MS = 24 * 60 * 60 * 1000; // 24h client lock in sessionStorage; server window is RATE_LIMIT_QUERY

export function isRateLimitMessage(message: string): boolean {
  return (
    /rate limit exceeded/i.test(message) ||
    /personal demo limit/i.test(message) ||
    /demo limit/i.test(message) ||
    /unlocks in/i.test(message)
  );
}

export function readLockUntil(): number | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const until = Number(raw);
    if (!Number.isFinite(until) || until <= Date.now()) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return until;
  } catch {
    return null;
  }
}

/** Start (or refresh) a 24-hour client lockout after a rate-limit response. */
export function engageRateLimitLock(): number {
  const until = Date.now() + LOCK_MS;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, String(until));
  } catch {
    /* ignore */
  }
  return until;
}

export function clearRateLimitLock(): void {
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function formatLockCountdown(remainingMs: number): string {
  const totalSec = Math.max(0, Math.ceil(remainingMs / 1000));
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = totalSec % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function rateLimitBannerMessage(countdown?: string | null): string {
  const wait = countdown
    ? ` Unlocks in ${countdown}.`
    : " This tab unlocks Ask and Upload in about 24 hours, or sooner if you close it.";
  return (
    "Personal demo limit: 10 Ask requests per visitor IP per day. After a 429, " +
    "this tab also locks Ask and Upload to keep the demo usable. " +
    "Configured owner accounts are exempt." +
    wait
  );
}
