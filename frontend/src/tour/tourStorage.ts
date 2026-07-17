const TOUR_PREFIX = "rag_tour_done";

function keyFor(userKey: string): string {
  return `${TOUR_PREFIX}:${userKey.toLowerCase()}`;
}

export function hasCompletedTour(userKey: string | null): boolean {
  if (!userKey) {
    return false;
  }
  return localStorage.getItem(keyFor(userKey)) === "true";
}

export function markTourComplete(userKey: string | null): void {
  if (!userKey) {
    return;
  }
  localStorage.setItem(keyFor(userKey), "true");
}

export function clearTourComplete(userKey: string | null): void {
  if (!userKey) {
    return;
  }
  localStorage.removeItem(keyFor(userKey));
}
