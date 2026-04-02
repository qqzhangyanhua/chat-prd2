"use client";

import { useWorkspaceStore } from "../../store/workspace-store";
import { AssistantTurnCard } from "./assistant-turn-card";
import { Composer } from "./composer";


interface ConversationPanelProps {
  sessionId: string;
}


export function ConversationPanel({ sessionId }: ConversationPanelProps) {
  const currentAction = useWorkspaceStore((state) => state.currentAction);
  const messages = useWorkspaceStore((state) => state.messages);
  const latestAssistantMessage =
    [...messages].reverse().find((message) => message.role === "assistant")
      ?.content ?? "";

  return (
    <section className="flex flex-col gap-5">
      <AssistantTurnCard
        currentAction={currentAction}
        latestAssistantMessage={latestAssistantMessage}
      />
      <Composer sessionId={sessionId} />
    </section>
  );
}
