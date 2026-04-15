"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { Send, Square, Loader } from "lucide-react";

import { getSession, regenerateMessage, sendMessage } from "../../lib/api";
import {
  getRecoveryActionFromError,
  resolveRecoveryAction,
  type ResolvedRecoveryAction,
} from "../../lib/recovery-action";
import { parseEventStream } from "../../lib/sse";
import { handleStreamError } from "../../lib/stream-error";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { useWorkspaceStore, workspaceStore } from "../../store/workspace-store";
import { ModelSelector } from "./model-selector";
import { WorkspaceErrorNotice } from "./workspace-error-notice";

interface ComposerProps {
  inputRef?: RefObject<HTMLTextAreaElement | null>;
  regenerateUserMessageId?: string | null;
  sessionId: string;
}

interface SuggestedModelSelection {
  modelConfigId: string;
  modelName: string;
  scene: string | null;
  reason: string | null;
}

interface PostModelSwitchPrompt {
  actionLabel: string;
  message: string;
  onAction: () => void;
}

function getSuggestedModelSelection(
  error: unknown,
  availableModelConfigs: Array<{ id: string; name: string }>,
): SuggestedModelSelection | null {
  if (
    typeof error !== "object" ||
    error === null ||
    !("details" in error) ||
    typeof (error as { details?: unknown }).details !== "object" ||
    (error as { details?: unknown }).details === null
  ) {
    return null;
  }

  const details = (error as {
    details: {
      recommended_model_config_id?: unknown;
      recommended_model_scene?: unknown;
      recommended_model_name?: unknown;
      recommended_model_reason?: unknown;
    };
  }).details;
  const recommendedModelConfigId = details.recommended_model_config_id;
  if (typeof recommendedModelConfigId !== "string") {
    return null;
  }

  const matchedModel = availableModelConfigs.find((item) => item.id === recommendedModelConfigId);
  if (!matchedModel) {
    return null;
  }

  return {
    modelConfigId: recommendedModelConfigId,
    modelName:
      typeof details.recommended_model_name === "string" && details.recommended_model_name
        ? details.recommended_model_name
        : matchedModel.name,
    scene:
      typeof details.recommended_model_scene === "string" && details.recommended_model_scene
        ? details.recommended_model_scene
        : null,
    reason:
      typeof details.recommended_model_reason === "string" && details.recommended_model_reason
        ? details.recommended_model_reason
        : null,
  };
}

function getSceneLabel(scene: string | null): string | null {
  if (scene === "general") {
    return "通用对话";
  }
  if (scene === "reasoning") {
    return "长文本推理";
  }
  if (scene === "fallback") {
    return "兜底回退";
  }
  return null;
}

function buildPostSwitchMessage(
  suggestedModel: SuggestedModelSelection,
  fallbackMessage: string,
): string {
  const parts = [`已切换到 ${suggestedModel.modelName}。`];
  const sceneLabel = getSceneLabel(suggestedModel.scene);
  if (sceneLabel) {
    parts.push(`按当前对话场景优先推荐：${sceneLabel}。`);
  }
  if (suggestedModel.reason) {
    parts.push(suggestedModel.reason);
  } else {
    parts.push(fallbackMessage);
  }
  return parts.join("");
}

export function Composer({
  sessionId,
  regenerateUserMessageId = null,
  inputRef,
}: ComposerProps) {
  const abortControllerRef = useRef<AbortController | null>(null);
  const manualDispatchRef = useRef(false);
  const lastHandledRegenerateIdRef = useRef(0);
  const modelSelectorRef = useRef<HTMLSelectElement | null>(null);
  const [errorRecoveryAction, setErrorRecoveryAction] = useState<ResolvedRecoveryAction | null>(null);
  const [postModelSwitchPrompt, setPostModelSwitchPrompt] = useState<PostModelSwitchPrompt | null>(null);
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
      manualDispatchRef.current = true;
    }

    if (!skipStartRequest) {
      workspaceStore.getState().startRequest(normalizedContent);
    }
    setErrorRecoveryAction(null);
    setPostModelSwitchPrompt(null);

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
      await refreshSessionSnapshot();
      setErrorRecoveryAction(null);
    } catch (error) {
      const wasAborted = handleStreamError({
        error,
        sessionId,
        showToast,
        toastId: `send-message-${sessionId}`,
        fallbackMessage: "消息发送失败",
      });
      if (wasAborted) {
        setErrorRecoveryAction(null);
        return;
      }

      const suggestedModel = getSuggestedModelSelection(error, availableModelConfigs);
      const resolvedAction = resolveRecoveryAction(getRecoveryActionFromError(error), {
        onSelectAvailableModel: () => {
          if (suggestedModel) {
            workspaceStore.getState().selectModelConfig(suggestedModel.modelConfigId);
            workspaceStore.getState().resetError();
            setErrorRecoveryAction(null);
            setPostModelSwitchPrompt({
              actionLabel: "立即重试刚才的消息",
              message: buildPostSwitchMessage(
                suggestedModel,
                "这个模型当前可用，我建议先继续刚才这条消息。",
              ),
              onAction: () => {
                setPostModelSwitchPrompt(null);
                void dispatchMessage(normalizedContent);
              },
            });
            return;
          }
          modelSelectorRef.current?.focus();
        },
      });

      setErrorRecoveryAction(
        suggestedModel && resolvedAction?.type === "select_available_model"
          ? {
              ...resolvedAction,
              label: `切换到 ${suggestedModel.modelName}`,
            }
          : resolvedAction,
      );
    } finally {
      if (!skipStartRequest) {
        manualDispatchRef.current = false;
      }
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
    setErrorRecoveryAction(null);
    setPostModelSwitchPrompt(null);

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
      await refreshSessionSnapshot();
      setErrorRecoveryAction(null);
    } catch (error) {
      const wasAborted = handleStreamError({
        error,
        sessionId,
        showToast,
        toastId: `regenerate-message-${sessionId}`,
        fallbackMessage: "消息重生成失败",
      });
      if (wasAborted) {
        setErrorRecoveryAction(null);
        return;
      }

      const suggestedModel = getSuggestedModelSelection(error, availableModelConfigs);
      const resolvedAction = resolveRecoveryAction(getRecoveryActionFromError(error), {
        onSelectAvailableModel: () => {
          if (suggestedModel) {
            workspaceStore.getState().selectModelConfig(suggestedModel.modelConfigId);
            workspaceStore.getState().resetError();
            setErrorRecoveryAction(null);
            setPostModelSwitchPrompt({
              actionLabel: "立即重新生成",
              message: buildPostSwitchMessage(
                suggestedModel,
                "这个模型当前可用，我建议先重新生成上一版回复。",
              ),
              onAction: () => {
                setPostModelSwitchPrompt(null);
                void dispatchRegenerate(userMessageId);
              },
            });
            return;
          }
          modelSelectorRef.current?.focus();
        },
      });

      setErrorRecoveryAction(
        suggestedModel && resolvedAction?.type === "select_available_model"
          ? {
              ...resolvedAction,
              label: `切换到 ${suggestedModel.modelName}`,
            }
          : resolvedAction,
      );
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
    }
  }

  async function refreshSessionSnapshot() {
    try {
      const snapshot = await getSession(sessionId, accessToken);
      workspaceStore.getState().refreshSessionSnapshot(snapshot);
    } catch (error) {
      console.error("刷新会话快照失败", error);
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

  // 处理从 workspace/new 页面跳转过来时的自动发送
  useEffect(() => {
    if (
      manualDispatchRef.current ||
      pendingRequestMode !== "new" ||
      !pendingUserInput ||
      !selectedModelConfigId
    ) {
      return;
    }
    void dispatchMessage(pendingUserInput, true);
  }, [pendingRequestMode, pendingUserInput, selectedModelConfigId]);

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
              ref={inputRef}
              onChange={(event) => {
                resetError();
                setPostModelSwitchPrompt(null);
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
            <ModelSelector
              onSelectModel={() => {
                resetError();
                setErrorRecoveryAction(null);
              }}
              selectRef={modelSelectorRef}
            />
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
              <WorkspaceErrorNotice
                actionLabel={errorRecoveryAction?.onAction ? errorRecoveryAction.label : undefined}
                className="mt-2"
                message={errorMessage}
                onAction={errorRecoveryAction?.onAction}
              />
            ) : null}
            {postModelSwitchPrompt ? (
              <div className="mt-2 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4 text-sm text-stone-700">
                <p>{postModelSwitchPrompt.message}</p>
                <button
                  type="button"
                  className="mt-3 rounded-xl border border-stone-300 bg-white px-4 py-2 font-medium text-stone-900"
                  onClick={postModelSwitchPrompt.onAction}
                >
                  {postModelSwitchPrompt.actionLabel}
                </button>
              </div>
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
