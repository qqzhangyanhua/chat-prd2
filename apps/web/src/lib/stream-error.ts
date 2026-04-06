import { workspaceStore } from "../store/workspace-store";

interface ShowToastFn {
  (opts: { id: string; message: string; tone: "info" | "error" | "success" }): void;
}

interface HandleStreamErrorOptions {
  error: unknown;
  sessionId: string;
  showToast: ShowToastFn;
  /** Toast id prefix used for non-abort errors, e.g. "send-message" or "regenerate-message" */
  toastId: string;
  /** Fallback message for non-abort errors */
  fallbackMessage: string;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error && error.name === "AbortError";
}

/**
 * Shared error handler for SSE streaming operations (send + regenerate).
 * Returns `true` when the error was a user-initiated abort, `false` otherwise.
 */
export function handleStreamError({
  error,
  sessionId,
  showToast,
  toastId,
  fallbackMessage,
}: HandleStreamErrorOptions): boolean {
  if (isAbortError(error)) {
    const { markInterrupted, resetError, setStreaming, streamPhase } =
      workspaceStore.getState();

    if (streamPhase === "streaming") {
      markInterrupted();
    } else {
      setStreaming(false);
    }

    resetError();
    showToast({
      id: `cancel-generation-${sessionId}`,
      message: "已停止本轮生成",
      tone: "info",
    });
    return true;
  }

  const message = error instanceof Error ? error.message : fallbackMessage;
  workspaceStore.getState().failRequest(message);
  showToast({ id: toastId, message, tone: "error" });
  return false;
}
