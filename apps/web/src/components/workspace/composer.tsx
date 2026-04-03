"use client";

import { useEffect, useRef } from "react";

import { sendMessage } from "../../lib/api";
import { parseEventStream } from "../../lib/sse";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { useWorkspaceStore, workspaceStore } from "../../store/workspace-store";

interface ComposerProps {
  sessionId: string;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error && error.name === "AbortError";
}

export function Composer({ sessionId }: ComposerProps) {
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastHandledRegenerateIdRef = useRef(0);
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);
  const errorMessage = useWorkspaceStore((state) => state.errorMessage);
  const inputValue = useWorkspaceStore((state) => state.inputValue);
  const isStreaming = useWorkspaceStore((state) => state.isStreaming);
  const pendingRequestMode = useWorkspaceStore((state) => state.pendingRequestMode);
  const pendingUserInput = useWorkspaceStore((state) => state.pendingUserInput);
  const regenerateRequestId = useWorkspaceStore((state) => state.regenerateRequestId);
  const streamPhase = useWorkspaceStore((state) => state.streamPhase);
  const resetError = useWorkspaceStore((state) => state.resetError);
  const setInputValue = useWorkspaceStore((state) => state.setInputValue);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
    };
  }, []);

  async function dispatchMessage(content: string, skipStartRequest = false) {
    const normalizedContent = content.trim();
    if (!normalizedContent || (isStreaming && !skipStartRequest)) {
      return;
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    if (!skipStartRequest) {
      workspaceStore.getState().startRequest(normalizedContent);
    }

    try {
      const stream = await sendMessage(
        sessionId,
        normalizedContent,
        accessToken,
        abortController.signal,
      );
      for await (const event of parseEventStream(stream)) {
        workspaceStore.getState().applyEvent(event);
      }
      if (workspaceStore.getState().isStreaming) {
        workspaceStore.getState().setStreaming(false);
      }
    } catch (error) {
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
        return;
      }

      const message = error instanceof Error ? error.message : "消息发送失败";
      workspaceStore.getState().failRequest(message);
      showToast({
        id: `send-message-${sessionId}`,
        message,
        tone: "error",
      });
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
    }
  }

  async function handleSend() {
    await dispatchMessage(inputValue);
  }

  function handleCancel() {
    abortControllerRef.current?.abort();
  }

  useEffect(() => {
    if (
      regenerateRequestId === 0 ||
      regenerateRequestId === lastHandledRegenerateIdRef.current ||
      pendingRequestMode !== "regenerate" ||
      !pendingUserInput
    ) {
      return;
    }

    lastHandledRegenerateIdRef.current = regenerateRequestId;
    void dispatchMessage(pendingUserInput, true);
  }, [pendingRequestMode, pendingUserInput, regenerateRequestId]);

  const statusMessage =
    streamPhase === "waiting"
      ? "正在等待智能体回应..."
      : streamPhase === "streaming"
        ? "正在生成回复..."
        : "优先用选择推进，必要时再补自由输入。";

  return (
    <form
      className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="block">
        <span className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
          当前输入
        </span>
        <textarea
          className="mt-3 min-h-32 w-full resize-none rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4 text-sm leading-7 text-stone-800 outline-none transition focus:border-stone-900"
          onChange={(event) => {
            resetError();
            setInputValue(event.target.value);
          }}
          placeholder="补充你的目标用户、真实场景、当前做法，或者直接回答上一轮问题。"
          value={inputValue}
        />
      </label>

      <div className="mt-4 flex items-center justify-between gap-4">
        <div className="space-y-1">
          <p className="text-sm text-stone-500">{statusMessage}</p>
          {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}
        </div>
        <button
          className="rounded-2xl bg-stone-900 px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-stone-400"
          onClick={() => {
            if (isStreaming) {
              handleCancel();
              return;
            }
            void handleSend();
          }}
          type="button"
        >
          {isStreaming ? "停止生成" : "发送消息"}
        </button>
      </div>
    </form>
  );
}
