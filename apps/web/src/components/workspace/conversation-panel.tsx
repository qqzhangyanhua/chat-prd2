"use client";

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
  const pendingRequestMode = useWorkspaceStore((state) => state.pendingRequestMode);
  const messages = useWorkspaceStore((state) => state.messages);
  const latestAssistantMessage =
    [...messages].reverse().find((message) => message.role === "assistant")?.content ?? "";

  return (
    <section className="flex flex-col gap-5">
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
