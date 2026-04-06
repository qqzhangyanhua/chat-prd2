"use client";

import { useEffect, useState } from "react";

import { getSession, listEnabledModelConfigs } from "../../lib/api";
import { consumeNewSessionDraft } from "../../lib/new-session-draft";
import { useAuthStore } from "../../store/auth-store";
import { useAuthGuard } from "../../hooks/use-auth-guard";
import { useToastStore } from "../../store/toast-store";
import { workspaceStore } from "../../store/workspace-store";
import { ConversationPanel } from "./conversation-panel";
import { PrdPanel } from "./prd-panel";
import { SkeletonCard } from "./skeleton-card";
import { WorkspaceLayout } from "./workspace-layout";

interface WorkspaceSessionShellProps {
  sessionId: string;
}

export function WorkspaceSessionShell({ sessionId }: WorkspaceSessionShellProps) {
  const { hydrated } = useAuthGuard();
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryToken, setRetryToken] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!hydrated) return;

    let cancelled = false;

    async function loadSession() {
      try {
        try {
          const snapshot = await getSession(sessionId, accessToken);
          if (cancelled) return;
          setLoadError(null);
          workspaceStore.getState().hydrateSession(snapshot);
          const pendingDraft = consumeNewSessionDraft(sessionId);
          if (pendingDraft) workspaceStore.getState().setInputValue(pendingDraft);
        } catch (error) {
          if (!cancelled) {
            const message = error instanceof Error ? error.message : "会话加载失败";
            workspaceStore.setState(workspaceStore.getInitialState(), true);
            setLoadError(message);
            showToast({ id: `load-session-${sessionId}`, message, tone: "error" });
          }
          return;
        }

        try {
          const enabledModelConfigs = await listEnabledModelConfigs(accessToken);
          if (!cancelled) workspaceStore.getState().setAvailableModelConfigs(enabledModelConfigs.items);
        } catch (error) {
          if (!cancelled) {
            workspaceStore.getState().setAvailableModelConfigs([]);
            const message = error instanceof Error ? error.message : "模型列表加载失败";
            showToast({ id: `load-model-configs-${sessionId}`, message, tone: "error" });
          }
        }
      } finally {
        if (!cancelled) {
          setIsRetrying(false);
          setIsLoading(false);
        }
      }
    }

    void loadSession();
    return () => { cancelled = true; };
  }, [hydrated, accessToken, retryToken, sessionId, showToast]);

  return (
    <WorkspaceLayout sessionId={sessionId}>
      {/* Conversation column */}
      <section className="flex flex-1 min-w-0 flex-col gap-4 overflow-y-auto">
        {isLoading ? (
          <div data-testid="session-loading-skeleton" className="flex flex-col gap-5">
            <SkeletonCard className="h-64" />
            <SkeletonCard className="h-32" />
          </div>
        ) : loadError ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-800">
            <p>{loadError}</p>
            <button
              type="button"
              disabled={isRetrying}
              className="mt-3 rounded-xl border border-red-300 bg-white px-4 py-2 font-medium text-red-700 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => { setIsRetrying(true); setRetryToken((n) => n + 1); }}
            >
              {isRetrying ? "重试中..." : "重试加载"}
            </button>
          </div>
        ) : (
          <ConversationPanel sessionId={sessionId} />
        )}
      </section>

      {/* PRD column */}
      {isLoading ? (
        <SkeletonCard className="h-full w-[360px] shrink-0" />
      ) : !loadError ? (
        <PrdPanel />
      ) : (
        <div className="h-full w-[360px] shrink-0 rounded-2xl border border-dashed border-stone-200/80 bg-white/60 p-6 text-sm text-stone-400 shadow-[0_2px_12px_rgba(0,0,0,0.04)]">
          当前会话加载失败，暂不展示 PRD 快照。
        </div>
      )}
    </WorkspaceLayout>
  );
}
