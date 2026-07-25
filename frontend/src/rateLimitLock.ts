const STORAGE_PREFIX = "rag_query_lock_until";
const LOCK_MS = 24 * 60 * 60 * 1000; // 24h client lock; server window is RATE_LIMIT_QUERY

function lockKey(userKey: string | null | undefined): string {
  return userKey ? `${STORAGE_PREFIX}:${userKey.toLowerCase()}` : STORAGE_PREFIX;
}

// Signed-in accounts lock in localStorage so the block follows the account
// across tabs; anonymous visitors fall back to per-tab sessionStorage.
function lockStore(userKey: string | null | undefined): Storage | null {
  try {
    return userKey ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

export function isRateLimitMessage(message: string): boolean {
  return (
    /rate limit exceeded/i.test(message) ||
    /personal demo limit/i.test(message) ||
    /demo limit/i.test(message) ||
    /unlocks in/i.test(message)
  );
}

export function readLockUntil(userKey: string | null | undefined): number | null {
  if (typeof window === "undefined") {
    return null;
  }
  const store = lockStore(userKey);
  if (!store) {
    return null;
  }
  try {
    const raw = store.getItem(lockKey(userKey));
    if (!raw) {
      return null;
    }
    const until = Number(raw);
    if (!Number.isFinite(until) || until <= Date.now()) {
      store.removeItem(lockKey(userKey));
      return null;
    }
    return until;
  } catch {
    return null;
  }
}

/** Start (or refresh) a 24-hour client lockout after a rate-limit response. */
export function engageRateLimitLock(userKey: string | null | undefined): number {
  const until = Date.now() + LOCK_MS;
  try {
    lockStore(userKey)?.setItem(lockKey(userKey), String(until));
  } catch {
    /* ignore */
  }
  return until;
}

export function clearRateLimitLock(userKey: string | null | undefined): void {
  try {
    lockStore(userKey)?.removeItem(lockKey(userKey));
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
    : " Ask and Upload unlock in about 24 hours.";
  return (
    "Personal demo limit: 10 Ask requests per account per day. After a too many requests " +
    "(429) response, this account locks Ask and Upload to keep the demo usable. " +
    "Configured owner accounts are exempt." +
    wait
  );
}
