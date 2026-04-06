"use client";

import { useEffect, useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { getSession } from "../../lib/api";
import { useAuthStore } from "../../store/auth-store";
import { useAuthGuard } from "../../hooks/use-auth-guard";
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
  useAuthGuard();
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryToken, setRetryToken] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadSession() {
      try {
        const snapshot = await getSession(sessionId, accessToken);
        if (!cancelled) {
          setLoadError(null);
          workspaceStore.getState().hydrateSession(snapshot);
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "会话加载失败";
          setLoadError(message);
          showToast({
            id: `load-session-${sessionId}`,
            message,
            tone: "error",
          });
        }
      } finally {
        if (!cancelled) {
          setIsRetrying(false);
        }
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
    };
  }, [accessToken, retryToken, sessionId, showToast]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.12),_transparent_28%),linear-gradient(180deg,_#f5f5f4_0%,_#fafaf9_48%,_#f5f5f4_100%)] px-4 py-4 md:px-6 md:py-6">
      <WorkspaceToastViewport />
      <div className={`mx-auto flex max-w-[1600px] flex-col gap-4 lg:grid transition-[grid-template-columns] duration-300 ${sidebarCollapsed ? "lg:grid-cols-[0px_minmax(0,1fr)_360px]" : "lg:grid-cols-[280px_minmax(0,1fr)_360px]"}`}>
        <div className={`relative transition-all duration-300 ${sidebarCollapsed ? "lg:overflow-hidden lg:w-0 lg:opacity-0" : "lg:opacity-100"}`}>
          <SessionSidebar sessionId={sessionId} />
        </div>
        <button
          type="button"
          onClick={() => setSidebarCollapsed((c) => !c)}
          className="fixed left-2 top-1/2 z-30 -translate-y-1/2 hidden lg:flex h-8 w-8 items-center justify-center rounded-full border border-stone-200 bg-white/90 text-stone-500 shadow-md transition-all duration-150 hover:bg-stone-50 hover:text-stone-900 active:scale-95"
          aria-label={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
          style={sidebarCollapsed ? {} : { left: "268px" }}
        >
          {sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
        <section className="flex flex-col gap-4">
          {loadError ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-800">
              <p>{loadError}</p>
              <button
                className="mt-3 rounded-xl border border-red-300 bg-white px-4 py-2 font-medium text-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isRetrying}
                onClick={() => {
                  setIsRetrying(true);
                  setRetryToken((current) => current + 1);
                }}
                type="button"
              >
                {isRetrying ? "重试中..." : "重试加载"}
              </button>
            </div>
          ) : null}
          <ConversationPanel sessionId={sessionId} />
        </section>
        <PrdPanel />
      </div>
    </main>
  );
}
