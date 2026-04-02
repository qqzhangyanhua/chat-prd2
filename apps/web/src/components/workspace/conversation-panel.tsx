import { AssistantTurnCard } from "./assistant-turn-card";
import { Composer } from "./composer";


export function ConversationPanel() {
  return (
    <section className="flex flex-col gap-5">
      <AssistantTurnCard />
      <Composer />
    </section>
  );
}
