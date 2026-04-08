"use client";

interface WorkspaceErrorNoticeProps {
  actionLabel?: string;
  actionPending?: boolean;
  className?: string;
  message: string;
  onAction?: () => void;
}

export function WorkspaceErrorNotice({
  actionLabel,
  actionPending = false,
  className,
  message,
  onAction,
}: WorkspaceErrorNoticeProps) {
  return (
    <div
      data-testid="workspace-error-notice"
      className={`rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-800 ${className ?? ""}`}
    >
      <p>{message}</p>
      {actionLabel && onAction ? (
        <button
          type="button"
          disabled={actionPending}
          className="mt-3 rounded-xl border border-red-300 bg-white px-4 py-2 font-medium text-red-700 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={onAction}
        >
          {actionPending ? "重试中..." : actionLabel}
        </button>
      ) : null}
    </div>
  );
}
