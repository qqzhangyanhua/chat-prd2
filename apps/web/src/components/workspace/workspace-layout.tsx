import { WorkspaceLeftNav } from "./workspace-left-nav";
import { WorkspaceToastViewport } from "./workspace-toast-viewport";

interface WorkspaceLayoutProps {
  sessionId?: string;
  children: React.ReactNode;
}

export function WorkspaceLayout({ sessionId, children }: WorkspaceLayoutProps) {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.12),_transparent_28%),linear-gradient(180deg,_#f5f5f4_0%,_#fafaf9_48%,_#f5f5f4_100%)] px-4 py-4 md:px-6 md:py-6">
      <WorkspaceToastViewport />
      <div className="mx-auto flex h-[calc(100vh-2rem)] max-w-[1600px] gap-4 md:h-[calc(100vh-3rem)]">
        <WorkspaceLeftNav sessionId={sessionId} />
        {children}
      </div>
    </main>
  );
}
