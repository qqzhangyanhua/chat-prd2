"use client";

import { useEffect, useRef } from "react";
import { Send, Square, Loader } from "lucide-react";

import { sendMessage } from "../../lib/api";
import { parseEventStream } from "../../lib/sse";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { useWorkspaceStore, workspaceStore } from "../../store/workspace-store";
import { ModelSelector } from "./model-selector";

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
  const availableModelConfigs = useWorkspaceStore((state) => state.availableModelConfigs);
  const errorMessage = useWorkspaceStore((state) => state.errorMessage);
  const inputValue = useWorkspaceStore((state) => state.inputValue);
  const isStreaming = useWorkspaceStore((state) => state.isStreaming);
  const pendingRequestMode = useWorkspaceStore((state) => state.pendingRequestMode);
  const pendingUserInput = useWorkspaceStore((state) => state.pendingUserInput);
  const regenerateRequestId = useWorkspaceStore((state) => state.regenerateRequestId);
  const selectedModelConfigId = useWorkspaceStore((state) => state.selectedModelConfigId);
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
    const modelConfigId = workspaceStore.getState().selectedModelConfigId;
    if (!normalizedContent || !modelConfigId || (isStreaming && !skipStartRequest)) {
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
        modelConfigId,
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
      ? "等待回应..."
      : streamPhase === "streaming"
        ? "正在生成回复..."
        : "准备好继续，补充你的想法";

  const isWaiting = streamPhase === "waiting";
  const hasAvailableModels = availableModelConfigs.length > 0;
  const sendDisabled = !isStreaming && (!inputValue.trim() || !selectedModelConfigId);

  return (
    <div className="rounded-2xl border border-stone-200/80 bg-white shadow-[0_2px_12px_rgba(0,0,0,0.04)]">
      <form onSubmit={(event) => event.preventDefault()}>
        <div className="px-5 pt-5">
          <label className="block">
            <span className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400">
              继续补充
            </span>
            <textarea
              className="mt-2.5 min-h-28 w-full resize-none rounded-xl border border-stone-200 bg-stone-50 px-4 py-3.5 text-sm leading-7 text-stone-800 placeholder:text-stone-400 outline-none transition-all duration-150 hover:border-stone-300 focus:border-stone-900 focus:bg-white focus:ring-2 focus:ring-stone-900/8 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isStreaming}
              onChange={(event) => {
                resetError();
                setInputValue(event.target.value);
              }}
              placeholder="把你现在的想法、顾虑或选择告诉我，AI 会基于上下文继续追问和收敛..."
              value={inputValue}
            />
          </label>
        </div>

        <div className="flex items-center justify-between gap-4 border-t border-stone-100 px-5 py-3.5">
          <div className="flex flex-col gap-0.5">
            <ModelSelector />
            <p className={`flex items-center gap-1.5 text-xs ${isWaiting || isStreaming ? "text-amber-600" : "text-stone-400"}`}>
              {isWaiting ? (
                <Loader className="h-3 w-3 animate-spin" />
              ) : isStreaming ? (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
              ) : null}
              {statusMessage}
            </p>
            {!hasAvailableModels ? (
              <p className="text-xs text-amber-700">当前没有可用模型，请先启用至少一个模型配置。</p>
            ) : null}
            {errorMessage ? (
              <p className="text-xs text-red-600">{errorMessage}</p>
            ) : null}
          </div>

          <button
            className={`flex cursor-pointer items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all duration-150 active:scale-[0.97] disabled:cursor-not-allowed ${
              isStreaming
                ? "bg-stone-100 text-stone-700 hover:bg-stone-200"
                : "bg-stone-950 text-white hover:bg-stone-800 disabled:bg-stone-300 disabled:text-stone-500"
            }`}
            disabled={sendDisabled}
            onClick={() => {
              if (isStreaming) {
                handleCancel();
                return;
              }
              void handleSend();
            }}
            type="button"
          >
            {isStreaming ? (
              <>
                <Square className="h-3.5 w-3.5 fill-current" />
                停止生成
              </>
            ) : (
              <>
                <Send className="h-3.5 w-3.5" />
                发送消息
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
