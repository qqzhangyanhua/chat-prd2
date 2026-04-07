"use client";

interface SchemaOutdatedNoticeProps {
  detail: string;
  missingTables?: string[];
}

export function SchemaOutdatedNotice({
  detail,
  missingTables = [],
}: SchemaOutdatedNoticeProps) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900 shadow-[0_2px_12px_rgba(0,0,0,0.04)]">
      <p className="text-base font-semibold">后端数据库迁移未完成</p>
      <p className="mt-2 leading-6">{detail}</p>
      <p className="mt-3 font-medium">建议立即执行：</p>
      <pre className="mt-2 overflow-x-auto rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs text-amber-950">
        <code>cd apps/api && alembic upgrade head</code>
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
    </div>
  );
}
