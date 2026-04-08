import type { ApiRecoveryAction } from "./types";

interface RecoveryActionHandlers {
  onLogin?: () => void;
  onOpenWorkspaceHome?: () => void;
  onReloadSession?: () => void;
  onRetry?: () => void;
  onRunMigration?: () => void;
  onSelectAvailableModel?: () => void;
}

export interface ResolvedRecoveryAction extends ApiRecoveryAction {
  onAction?: () => void;
}

export function getRecoveryActionFromError(error: unknown): ApiRecoveryAction | null {
  if (
    typeof error === "object" &&
    error !== null &&
    "recoveryAction" in error &&
    typeof (error as { recoveryAction?: unknown }).recoveryAction === "object" &&
    (error as { recoveryAction?: unknown }).recoveryAction !== null
  ) {
    return (error as { recoveryAction: ApiRecoveryAction }).recoveryAction;
  }

  return null;
}

export function resolveRecoveryAction(
  action: ApiRecoveryAction | null | undefined,
  handlers: RecoveryActionHandlers = {},
): ResolvedRecoveryAction | null {
  if (!action) {
    return null;
  }

  const handlerMap: Record<string, (() => void) | undefined> = {
    login: handlers.onLogin,
    open_workspace_home: handlers.onOpenWorkspaceHome,
    reload_session: handlers.onReloadSession,
    retry: handlers.onRetry,
    run_migration: handlers.onRunMigration,
    select_available_model: handlers.onSelectAvailableModel,
  };

  return {
    ...action,
    onAction: handlerMap[action.type],
  };
}
