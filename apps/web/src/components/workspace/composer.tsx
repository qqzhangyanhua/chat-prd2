"use client";

import { useEffect, useRef } from "react";
import { Send, Square, Loader } from "lucide-react";

import { regenerateMessage } from "../../lib/api";
import { sendMessage } from "../../lib/api";
import { parseEventStream } from "../../lib/sse";
import { handleStreamError } from "../../lib/stream-error";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { useWorkspaceStore, workspaceStore } from "../../store/workspace-store";
import { ModelSelector } from "./model-selector";

interface ComposerProps {
  regenerateUserMessageId?: string | null;
  sessionId: string;
}


export function Composer({ sessionId, regenerateUserMessageId = null }: ComposerProps) {
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
      const wasAborted = handleStreamError({
        error,
        sessionId,
        showToast,
        toastId: `send-message-${sessionId}`,
        fallbackMessage: "消息发送失败",
      });
      if (wasAborted) return;
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
    }
  }

  async function dispatchRegenerate(userMessageId: string) {
    const modelConfigId = workspaceStore.getState().selectedModelConfigId;
    if (!modelConfigId) {
      return;
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const stream = await regenerateMessage(
        sessionId,
        userMessageId,
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
      const wasAborted = handleStreamError({
        error,
        sessionId,
        showToast,
        toastId: `regenerate-message-${sessionId}`,
        fallbackMessage: "消息重生成失败",
      });
      if (wasAborted) return;
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

    if (!selectedModelConfigId || !regenerateUserMessageId) {
      workspaceStore.getState().cancelPendingRequest();
      return;
    }

    lastHandledRegenerateIdRef.current = regenerateRequestId;
    void dispatchRegenerate(regenerateUserMessageId);
  }, [
    pendingRequestMode,
    pendingUserInput,
    regenerateRequestId,
    regenerateUserMessageId,
    selectedModelConfigId,
  ]);

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
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (!isStreaming && !sendDisabled) {
                    void handleSend();
                  }
                }
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
              <p className="text-xs text-amber-700">当前暂无可用模型，请联系管理员配置。</p>
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
