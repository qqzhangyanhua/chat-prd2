"use client";

interface SchemaOutdatedNoticeProps {
  actionLabel?: string;
  actionPending?: boolean;
  command?: string;
  detail: string;
  missingTables?: string[];
  onAction?: () => void;
}

export function SchemaOutdatedNotice({
  actionLabel,
  actionPending = false,
  command = "cd apps/api && alembic upgrade head",
  detail,
  missingTables = [],
  onAction,
}: SchemaOutdatedNoticeProps) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900 shadow-[0_2px_12px_rgba(0,0,0,0.04)]">
      <p className="text-base font-semibold">后端数据库迁移未完成</p>
      <p className="mt-2 leading-6">{detail}</p>
      <p className="mt-3 font-medium">建议立即执行：</p>
      <pre className="mt-2 overflow-x-auto rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs text-amber-950">
        <code>{command}</code>
      </pre>
      {missingTables.length > 0 ? (
        <div className="mt-3">
          <p className="font-medium">缺失表：</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {missingTables.map((tableName) => (
              <span
                key={tableName}
                className="rounded-full border border-amber-200 bg-white px-2.5 py-1 text-xs font-medium text-amber-900"
              >
                {tableName}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {actionLabel && onAction ? (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            className="inline-flex items-center justify-center rounded-full border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-950 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={actionPending}
            type="button"
            onClick={onAction}
          >
            {actionPending ? "检测中..." : actionLabel}
          </button>
          <p className="text-xs text-amber-800">执行迁移后，可重新检测并继续进入工作区。</p>
        </div>
      ) : null}
    </div>
  );
}
