import { ConversationPanel } from "../../components/workspace/conversation-panel";
import { PrdPanel } from "../../components/workspace/prd-panel";
import { SessionSidebar } from "../../components/workspace/session-sidebar";


export default function WorkspacePage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.12),_transparent_28%),linear-gradient(180deg,_#f5f5f4_0%,_#fafaf9_48%,_#f5f5f4_100%)] px-4 py-4 md:px-6 md:py-6">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-4 lg:grid lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <SessionSidebar />
        <ConversationPanel />
        <PrdPanel />
      </div>
    </main>
  );
}
