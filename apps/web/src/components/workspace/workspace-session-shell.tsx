"use client";

import { useEffect } from "react";

import { getSession } from "../../lib/api";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { workspaceStore } from "../../store/workspace-store";
import { ConversationPanel } from "./conversation-panel";
import { PrdPanel } from "./prd-panel";
import { SessionSidebar } from "./session-sidebar";
import { WorkspaceToastViewport } from "./workspace-toast-viewport";

interface WorkspaceSessionShellProps {
  sessionId: string;
}

export function WorkspaceSessionShell({ sessionId }: WorkspaceSessionShellProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);

  useEffect(() => {
    let cancelled = false;

    async function loadSession() {
      try {
        const snapshot = await getSession(sessionId, accessToken);
        if (!cancelled) {
          workspaceStore.getState().hydrateSession(snapshot);
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            id: `load-session-${sessionId}`,
            message: error instanceof Error ? error.message : "会话加载失败",
            tone: "error",
          });
        }
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
    };
  }, [accessToken, sessionId, showToast]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.12),_transparent_28%),linear-gradient(180deg,_#f5f5f4_0%,_#fafaf9_48%,_#f5f5f4_100%)] px-4 py-4 md:px-6 md:py-6">
      <WorkspaceToastViewport />
      <div className="mx-auto flex max-w-[1600px] flex-col gap-4 lg:grid lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <SessionSidebar sessionId={sessionId} />
        <ConversationPanel sessionId={sessionId} />
        <PrdPanel />
      </div>
    </main>
  );
}
