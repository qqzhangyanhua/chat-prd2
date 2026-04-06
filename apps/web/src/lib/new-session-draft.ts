const NEW_SESSION_DRAFT_PREFIX = "ai-cofounder:new-session-draft:";

function getDraftKey(sessionId: string): string {
  return `${NEW_SESSION_DRAFT_PREFIX}${sessionId}`;
}

export function storeNewSessionDraft(sessionId: string, draft: string): void {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(getDraftKey(sessionId), draft);
}

export function consumeNewSessionDraft(sessionId: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const key = getDraftKey(sessionId);
  const draft = window.sessionStorage.getItem(key);
  if (draft === null) {
    return null;
  }

  window.sessionStorage.removeItem(key);
  return draft;
}
