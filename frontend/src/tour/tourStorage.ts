const TOUR_PREFIX = "rag_tour_done";
const CREATE_NUDGE_PREFIX = "rag_create_nudge_done";

function tourKey(userKey: string): string {
  return `${TOUR_PREFIX}:${userKey.toLowerCase()}`;
}

function createNudgeKey(userKey: string): string {
  return `${CREATE_NUDGE_PREFIX}:${userKey.toLowerCase()}`;
}

export function hasCompletedTour(userKey: string | null): boolean {
  if (!userKey) {
    return false;
  }
  return localStorage.getItem(tourKey(userKey)) === "true";
}

export function markTourComplete(userKey: string | null): void {
  if (!userKey) {
    return;
  }
  localStorage.setItem(tourKey(userKey), "true");
}

export function clearTourComplete(userKey: string | null): void {
  if (!userKey) {
    return;
  }
  localStorage.removeItem(tourKey(userKey));
}

export function hasDismissedCreateNudge(userKey: string | null): boolean {
  if (!userKey) {
    return true;
  }
  return localStorage.getItem(createNudgeKey(userKey)) === "true";
}

export function markCreateNudgeDone(userKey: string | null): void {
  if (!userKey) {
    return;
  }
  localStorage.setItem(createNudgeKey(userKey), "true");
}

export function clearCreateNudgeDone(userKey: string | null): void {
  if (!userKey) {
    return;
  }
  localStorage.removeItem(createNudgeKey(userKey));
}
