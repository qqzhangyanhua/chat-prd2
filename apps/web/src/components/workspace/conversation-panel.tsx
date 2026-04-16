"use client";

import { useEffect, useRef } from "react";

import { finalizeSession } from "../../lib/api";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import {
  buildDiagnosticLedgerGroups,
  workspaceStore,
  useWorkspaceStore,
} from "../../store/workspace-store";
import { AssistantTurnCard } from "./assistant-turn-card";
import { BrandIcon } from "./brand-icon";
import { Composer } from "./composer";
import { DiagnosticsLedgerCard } from "./diagnostics-ledger-card";
import { FirstDraftCard } from "./first-draft-card";

interface ConversationPanelProps {
  sessionId: string;
}

export function ConversationPanel({ sessionId }: ConversationPanelProps) {
  const composerInputRef = useRef<HTMLTextAreaElement | null>(null);
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);
  const currentAction = useWorkspaceStore((state) => state.currentAction);
  const isCompleted = useWorkspaceStore((state) => state.isCompleted);
  const isFinalizing = useWorkspaceStore((state) => state.isFinalizingSession);
  const isFinalizeReady = useWorkspaceStore((state) => state.isFinalizeReady);
  const isStreaming = useWorkspaceStore((state) => state.isStreaming);
  const lastInterrupted = useWorkspaceStore((state) => state.lastInterrupted);
  const messages = useWorkspaceStore((state) => state.messages);
  const pendingRequestMode = useWorkspaceStore((state) => state.pendingRequestMode);
  const pendingUserInput = useWorkspaceStore((state) => state.pendingUserInput);
  const replyGroups = useWorkspaceStore((state) => state.replyGroups);
  const selectedModelConfigId = useWorkspaceStore((state) => state.selectedModelConfigId);
  const decisionGuidance = useWorkspaceStore((state) => state.decisionGuidance);
  const collaborationModeLabel = useWorkspaceStore((state) => state.collaborationModeLabel);
  const latestDiagnostics = useWorkspaceStore((state) => state.latestDiagnostics);
  const latestDiagnosticSummary = useWorkspaceStore((state) => state.latestDiagnosticSummary);
  const diagnosticLedger = useWorkspaceStore((state) => state.diagnosticLedger);
  const diagnosticLedgerSummary = useWorkspaceStore((state) => state.diagnosticLedgerSummary);
  const firstDraft = useWorkspaceStore((state) => state.firstDraft);
  const prdMeta = useWorkspaceStore((state) => state.prd.meta);
  const streamPhase = useWorkspaceStore((state) => state.streamPhase);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [isStreaming, messages.length, pendingUserInput]);

  let lastAssistantIndex = messages.reduce(
    (latestIndex, message, index) => (message.role === "assistant" ? index : latestIndex),
    -1,
  );

  const isWaitingForNew = streamPhase === "waiting" && pendingRequestMode !== "regenerate";
  if (isWaitingForNew) {
    lastAssistantIndex = messages.length;
  }

  const latestAssistantMessage =
    lastAssistantIndex >= 0 && lastAssistantIndex < messages.length
      ? messages[lastAssistantIndex]?.content ?? "" 
      : "";
  const historyMessages = lastAssistantIndex >= 0 ? messages.slice(0, lastAssistantIndex) : messages;
  const latestAssistantMessageMeta =
    lastAssistantIndex >= 0 && lastAssistantIndex < messages.length 
      ? messages[lastAssistantIndex] ?? null 
      : null;
  const latestUserMessage =
    lastAssistantIndex >= 0
      ? [...messages.slice(0, lastAssistantIndex)].reverse().find((message) => message.role === "user") ?? null
      : null;
  const latestReplyVersions =
    latestAssistantMessageMeta?.replyGroupId
      ? (replyGroups[latestAssistantMessageMeta.replyGroupId]?.versions ?? []).map((version) => ({
          assistantVersionId: version.id,
          content: version.content,
          createdAt: version.createdAt,
          isLatest: version.isLatest,
          versionNo: version.versionNo,
        }))
      : [];
  const regenerateUserMessageId =
    latestAssistantMessageMeta?.replyGroupId
      ? replyGroups[latestAssistantMessageMeta.replyGroupId]?.userMessageId ?? null
      : null;

  const assistantStatus = (() => {
    if (isStreaming && pendingRequestMode === "regenerate") {
      return {
        label: "重新生成中",
        tone: "active" as const,
        hint: "正在基于同一轮问题生成新版本。",
      };
    }

    if (streamPhase === "waiting") {
      return {
        label: "等待回应",
        tone: "active" as const,
        hint: "已收到你的输入，正在组织下一轮回复。",
      };
    }

    if (isStreaming) {
      return {
        label: "生成回复中",
        tone: "active" as const,
        hint: "AI 正在补全当前回复。",
      };
    }

    if (lastInterrupted && latestAssistantMessage.length > 0) {
      return {
        label: "已暂停",
        tone: "warning" as const,
        hint: "你可以继续补充调整点，我会从当前上下文接着推进。",
      };
    }

    if (prdMeta.stageTone === "final") {
      return {
        label: prdMeta.stageLabel,
        tone: "success" as const,
        hint: "如果还想调整内容，直接继续说要改哪里，我会基于终稿继续修改。",
      };
    }

    if (prdMeta.stageTone === "ready") {
      return {
        label: prdMeta.stageLabel,
        tone: "neutral" as const,
        hint: prdMeta.nextQuestion ?? "当前信息已接近终稿，可以继续确认或补充细节。",
      };
    }

    if (decisionGuidance?.strategyLabel) {
      return {
        label: decisionGuidance.strategyLabel,
        tone: "active" as const,
        hint: null,
      };
    }

    return {
      label: prdMeta.stageLabel,
      tone: "active" as const,
      hint: null,
    };
  })();

  const hasNoHistory = historyMessages.length === 0 && !isStreaming;
  const shouldShowGuidance = streamPhase !== "waiting" && !isStreaming;
  const canFinalize = isFinalizeReady && !isCompleted;
  const isFinalizeDisabled = isFinalizing || isStreaming;

  async function handleFinalize() {
    if (workspaceStore.getState().isFinalizingSession || workspaceStore.getState().isStreaming) {
      return;
    }

    workspaceStore.getState().setSessionFinalizing(true);
    try {
      const snapshot = await finalizeSession(
        sessionId,
        { confirmation_source: "button" },
        accessToken,
      );
      workspaceStore.getState().refreshSessionSnapshot(snapshot);
      showToast({
        id: `session-finalize-${sessionId}`,
        message: "已生成最终版 PRD。",
        tone: "success",
      });
    } catch (error) {
      console.error("整理最终版 PRD 失败", error);
      showToast({
        id: `session-finalize-${sessionId}`,
        message: "生成最终版 PRD 失败，请稍后重试。",
        tone: "error",
      });
    } finally {
      workspaceStore.getState().setSessionFinalizing(false);
    }
  }

  return (
    <section className="flex flex-col gap-5">
      {(historyMessages.length > 0 || (isStreaming && pendingRequestMode === "new" && pendingUserInput)) ? (
        <div
          ref={scrollRef}
          className="flex max-h-[420px] flex-col gap-3 overflow-y-auto rounded-2xl border border-stone-200/80 bg-white p-4 shadow-[0_2px_12px_rgba(0,0,0,0.04)]"
        >
          {historyMessages.map((message, index) =>
            message.role === "user" ? (
              <div key={message.id ?? `${message.role}-${index}`} className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-stone-950 px-4 py-2.5 text-sm leading-6 text-white">
                  {message.content}
                </div>
              </div>
            ) : (
              <div key={message.id ?? `${message.role}-${index}`} className="flex justify-start">
                <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-stone-100 bg-stone-50 px-4 py-2.5 text-sm leading-6 text-stone-700">
                  {message.content}
                </div>
              </div>
            ),
          )}
          {isStreaming && pendingRequestMode === "new" && pendingUserInput ? (
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-stone-950 px-4 py-2.5 text-sm leading-6 text-white opacity-60">
                {pendingUserInput}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {hasNoHistory ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-stone-200/80 bg-white p-10 shadow-[0_2px_12px_rgba(0,0,0,0.04)]">
          <BrandIcon size="md" />
          <p className="text-sm font-semibold text-stone-900">开始描述你的想法</p>
          <p className="text-xs text-center text-stone-500 max-w-xs">
            在下方输入框告诉我你想解决的问题或构建的产品，我会帮你一步步梳理清楚。
          </p>
        </div>
      ) : (
        <AssistantTurnCard
          canRegenerate={Boolean(selectedModelConfigId && regenerateUserMessageId)}
          collaborationModeLabel={collaborationModeLabel}
          completedHint={
            isCompleted ? "已生成最终版，继续输入会重新打开编辑流程。" : null
          }
          currentAction={currentAction}
          isFinalizeDisabled={isFinalizeDisabled}
          statusBadge={assistantStatus}
          isFinalizing={isFinalizing}
          isRegenerating={isStreaming && pendingRequestMode === "regenerate"}
          isWaiting={isWaitingForNew}
          latestAssistantMessage={latestAssistantMessage}
          decisionGuidance={shouldShowGuidance ? decisionGuidance : null}
          latestDiagnostics={shouldShowGuidance ? latestDiagnostics : []}
          latestDiagnosticSummary={shouldShowGuidance ? latestDiagnosticSummary : null}
          onFinalize={handleFinalize}
          onSelectDecisionGuidanceQuestion={(question) =>
            workspaceStore.getState().setInputValue(question)
          }
          onRequestFreeSupplement={() => {
            composerInputRef.current?.focus();
          }}
          onRegenerate={() => {
            if (isStreaming) {
              return;
            }
            if (latestUserMessage?.content) {
              workspaceStore.setState((state) => ({
                ...state,
                lastSubmittedInput: latestUserMessage.content,
              }));
            }
            workspaceStore.getState().startRegenerate();
          }}
          replyVersions={latestReplyVersions}
          showFinalizeAction={canFinalize}
          showInterruptedMarker={lastInterrupted && latestAssistantMessage.length > 0}
        />
      )}
      <FirstDraftCard firstDraft={firstDraft} />
      <DiagnosticsLedgerCard
        groups={buildDiagnosticLedgerGroups(diagnosticLedger)}
        summary={diagnosticLedgerSummary}
      />
      <Composer
        inputRef={composerInputRef}
        sessionId={sessionId}
        regenerateUserMessageId={regenerateUserMessageId}
      />
    </section>
  );
}
