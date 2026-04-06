"use client";

import { useEffect, useRef } from "react";

import { workspaceStore, useWorkspaceStore } from "../../store/workspace-store";
import { AssistantTurnCard } from "./assistant-turn-card";
import { Composer } from "./composer";

interface ConversationPanelProps {
  sessionId: string;
}

export function ConversationPanel({ sessionId }: ConversationPanelProps) {
  const currentAction = useWorkspaceStore((state) => state.currentAction);
  const isStreaming = useWorkspaceStore((state) => state.isStreaming);
  const lastInterrupted = useWorkspaceStore((state) => state.lastInterrupted);
  const messages = useWorkspaceStore((state) => state.messages);
  const pendingRequestMode = useWorkspaceStore((state) => state.pendingRequestMode);
  const pendingUserInput = useWorkspaceStore((state) => state.pendingUserInput);
  const replyGroups = useWorkspaceStore((state) => state.replyGroups);
  const selectedModelConfigId = useWorkspaceStore((state) => state.selectedModelConfigId);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [isStreaming, messages.length, pendingUserInput]);

  const lastAssistantIndex = messages.reduce(
    (latestIndex, message, index) => (message.role === "assistant" ? index : latestIndex),
    -1,
  );

  const latestAssistantMessage =
    lastAssistantIndex >= 0 ? messages[lastAssistantIndex]?.content ?? "" : "";
  const historyMessages = lastAssistantIndex >= 0 ? messages.slice(0, lastAssistantIndex) : messages;
  const latestAssistantMessageMeta =
    lastAssistantIndex >= 0 ? messages[lastAssistantIndex] ?? null : null;
  const latestUserMessage =
    lastAssistantIndex >= 0
      ? [...messages.slice(0, lastAssistantIndex)].reverse().find((message) => message.role === "user") ?? null
      : null;
  const latestReplyVersions =
    latestAssistantMessageMeta?.replyGroupId
      ? (replyGroups[latestAssistantMessageMeta.replyGroupId]?.versions ?? []).map((version) => ({
          assistantVersionId: version.id,
          content: version.content,
          createdAt: undefined,
          isLatest: version.isLatest,
          versionNo: version.versionNo,
        }))
      : [];
  const regenerateUserMessageId =
    latestAssistantMessageMeta?.replyGroupId
      ? replyGroups[latestAssistantMessageMeta.replyGroupId]?.userMessageId ?? null
      : null;

  const hasNoHistory = historyMessages.length === 0 && !isStreaming;

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
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-primary to-brand-accent text-white">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" strokeLinejoin="round"/>
            </svg>
          </div>
          <p className="text-sm font-semibold text-stone-900">开始描述你的想法</p>
          <p className="text-xs text-center text-stone-500 max-w-xs">
            在下方输入框告诉我你想解决的问题或构建的产品，我会帮你一步步梳理清楚。
          </p>
        </div>
      ) : (
        <AssistantTurnCard
          canRegenerate={Boolean(selectedModelConfigId && regenerateUserMessageId)}
          currentAction={currentAction}
          isRegenerating={isStreaming && pendingRequestMode === "regenerate"}
          latestAssistantMessage={latestAssistantMessage}
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
          showInterruptedMarker={lastInterrupted && latestAssistantMessage.length > 0}
        />
      )}
      <Composer sessionId={sessionId} regenerateUserMessageId={regenerateUserMessageId} />
    </section>
  );
}
