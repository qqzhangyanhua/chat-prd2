"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getSession, listEnabledModelConfigs, SCHEMA_OUTDATED_DETAIL } from "../../lib/api";
import { useSchemaGate } from "../../hooks/use-schema-gate";
import { getRecoveryActionFromError, resolveRecoveryAction } from "../../lib/recovery-action";
import { consumeNewSessionDraft } from "../../lib/new-session-draft";
import { useAuthStore } from "../../store/auth-store";
import { useAuthGuard } from "../../hooks/use-auth-guard";
import { useToastStore } from "../../store/toast-store";
import { workspaceStore } from "../../store/workspace-store";
import { ConversationPanel } from "./conversation-panel";
import { PrdPanel } from "./prd-panel";
import { WorkspaceErrorNotice } from "./workspace-error-notice";
import { SchemaOutdatedNotice } from "./schema-outdated-notice";
import { SkeletonCard } from "./skeleton-card";
import { WorkspaceLayout } from "./workspace-layout";

interface WorkspaceSessionShellProps {
  sessionId: string;
  searchParams?: Promise<{ initial_idea?: string }>;
}

export function WorkspaceSessionShell({ sessionId, searchParams }: WorkspaceSessionShellProps) {
  const { push } = useRouter();
  const { hydrated } = useAuthGuard();
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);
  const [loadErrorCause, setLoadErrorCause] = useState<unknown>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryToken, setRetryToken] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [initialIdeaProcessed, setInitialIdeaProcessed] = useState(false);
  const {
    schemaHealth,
    clearSchemaHealth,
    checkSchemaGate,
    isCheckingSchema,
    syncSchemaFromError,
  } = useSchemaGate();
  const schemaRecoveryAction = resolveRecoveryAction(schemaHealth?.error?.recovery_action);
  const loadRecoveryAction = resolveRecoveryAction(getRecoveryActionFromError(loadErrorCause), {
    onOpenWorkspaceHome: () => {
      push("/workspace/home");
    },
    onReloadSession: () => {
      setIsRetrying(true);
      setRetryToken((n) => n + 1);
    },
    onRetry: () => {
      setIsRetrying(true);
      setRetryToken((n) => n + 1);
    },
  });

  useEffect(() => {
    if (!hydrated) return;

    let cancelled = false;

    async function loadSession() {
      try {
        try {
          const snapshot = await getSession(sessionId, accessToken);
          if (cancelled) return;
          setLoadErrorCause(null);
          setLoadError(null);
          clearSchemaHealth();
          workspaceStore.getState().hydrateSession(snapshot);
          const pendingDraft = consumeNewSessionDraft(sessionId);
          if (pendingDraft) workspaceStore.getState().setInputValue(pendingDraft);
          // 重置 initialIdeaProcessed，允许后续处理 initial_idea
          setInitialIdeaProcessed(false);
        } catch (error) {
          if (!cancelled) {
            const message = error instanceof Error ? error.message : "会话加载失败";
            workspaceStore.setState(workspaceStore.getInitialState(), true);
            setLoadErrorCause(error);
            setLoadError(message);
            await syncSchemaFromError(error);
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
  }, [hydrated, accessToken, retryToken, sessionId, showToast, clearSchemaHealth, syncSchemaFromError]);

  // 处理初始消息的自动发送
  useEffect(() => {
    if (!hydrated || isLoading || initialIdeaProcessed) return;

    async function processInitialIdea() {
      try {
        // 从 URL param 或 sessionStorage 读取 initial_idea
        let initialIdea: string | null = null;

        if (searchParams) {
          try {
            const params = await searchParams;
            initialIdea = params.initial_idea || null;
          } catch {
            // searchParams 解析失败，继续检查 sessionStorage
          }
        }

        if (!initialIdea && typeof window !== "undefined") {
          initialIdea = window.sessionStorage.getItem(`initial_idea_${sessionId}`);
          if (initialIdea) {
            window.sessionStorage.removeItem(`initial_idea_${sessionId}`);
          }
        }

        if (initialIdea) {
          // 设置输入值并自动发送
          workspaceStore.getState().setInputValue(initialIdea);
          // 触发消息发送（通过 startRequest）
          workspaceStore.getState().startRequest(initialIdea);
        }
      } finally {
        setInitialIdeaProcessed(true);
      }
    }

    void processInitialIdea();
  }, [hydrated, isLoading, sessionId, searchParams]);

  async function handleSchemaRetry() {
    setIsRetrying(true);

    const result = await checkSchemaGate({
      onReady: () => {
        setRetryToken((n) => n + 1);
      },
      onCheckFailed: (error) => {
        const message = error instanceof Error ? error.message : "健康检查失败";
        showToast({ id: `schema-recheck-${sessionId}`, message, tone: "error" });
      },
    });

    if (result !== "ready") {
      setIsRetrying(false);
    }
  }

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
          schemaHealth?.schema === "outdated" ? (
            <SchemaOutdatedNotice
              actionLabel="重新检测"
              actionPending={isRetrying || isCheckingSchema}
              command={schemaRecoveryAction?.type === "run_migration" ? schemaRecoveryAction.target ?? undefined : undefined}
              detail={schemaHealth.detail ?? SCHEMA_OUTDATED_DETAIL}
              missingTables={schemaHealth.missing_tables}
              onAction={handleSchemaRetry}
            />
          ) : (
            <WorkspaceErrorNotice
              actionLabel={loadRecoveryAction?.onAction ? loadRecoveryAction.label : "重试加载"}
              actionPending={isRetrying && !loadRecoveryAction?.onAction}
              message={loadError}
              onAction={loadRecoveryAction?.onAction ?? (() => {
                setIsRetrying(true);
                setRetryToken((n) => n + 1);
              })}
            />
          )
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
        <WorkspaceErrorNotice
          className="h-fit w-[360px] shrink-0"
          message="当前会话加载失败，暂不展示 PRD 快照。"
        />
      )}
    </WorkspaceLayout>
  );
}
