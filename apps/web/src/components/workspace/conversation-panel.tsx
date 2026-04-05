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
  const lastSubmittedInput = useWorkspaceStore((state) => state.lastSubmittedInput);
  const messages = useWorkspaceStore((state) => state.messages);
  const pendingRequestMode = useWorkspaceStore((state) => state.pendingRequestMode);
  const pendingUserInput = useWorkspaceStore((state) => state.pendingUserInput);
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

      <AssistantTurnCard
        canRegenerate={Boolean(lastSubmittedInput)}
        currentAction={currentAction}
        isRegenerating={isStreaming && pendingRequestMode === "regenerate"}
        latestAssistantMessage={latestAssistantMessage}
        onRegenerate={() => {
          if (isStreaming) {
            return;
          }
          workspaceStore.getState().startRegenerate();
        }}
        showInterruptedMarker={lastInterrupted && latestAssistantMessage.length > 0}
      />
      <Composer sessionId={sessionId} />
    </section>
  );
}
