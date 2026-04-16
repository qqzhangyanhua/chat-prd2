"use client";

import { Download, Flag, History, ShieldAlert, Sparkles } from "lucide-react";

import { useWorkspaceStore } from "../../store/workspace-store";

const replayIconMap = {
  guidance: Sparkles,
  diagnostics: ShieldAlert,
  prd_delta: History,
  finalize: Flag,
  export: Download,
} as const;

const replayLabelMap = {
  guidance: "Guidance Decision",
  diagnostics: "Diagnostics",
  prd_delta: "PRD Change",
  finalize: "Finalize Milestone",
  export: "Export Milestone",
} as const;

export function ReplayPanel() {
  const replayTimeline = useWorkspaceStore((state) => state.replayTimeline);

  return (
    <aside className="flex w-full flex-col rounded-2xl border border-stone-200/80 bg-white/90 p-4 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
      <div className="flex items-center gap-2.5 border-b border-stone-100 pb-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-stone-200 bg-stone-100">
          <History className="h-3.5 w-3.5 text-stone-500" />
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400">Replay</p>
          <h2 className="mt-0.5 text-sm font-semibold text-stone-950">Timeline</h2>
        </div>
      </div>

      {replayTimeline.length === 0 ? (
        <p className="mt-3 text-xs leading-5 text-stone-500">当前会话还没有可回放的关键节点。</p>
      ) : (
        <ol className="mt-4 flex flex-col gap-3">
          {replayTimeline.map((item) => {
            const Icon = replayIconMap[item.type];
            return (
              <li
                key={item.id}
                className="rounded-2xl border border-stone-200 bg-stone-50/70 px-3 py-3"
                data-testid={`replay-item-${item.type}`}
              >
                <div className="flex items-start gap-2.5">
                  <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-stone-200 bg-white">
                    <Icon className="h-3.5 w-3.5 text-stone-600" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold text-stone-900">{replayLabelMap[item.type] ?? item.title}</p>
                      {item.event_at ? (
                        <span className="text-[11px] text-stone-500">{item.event_at}</span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs leading-5 text-stone-600">{item.summary}</p>
                    {item.sections_changed && item.sections_changed.length > 0 ? (
                      <p className="mt-2 text-[11px] font-medium text-stone-500">
                        sections: {item.sections_changed.join(", ")}
                      </p>
                    ) : null}
                    {item.type === "export" && typeof item.metadata?.file_name === "string" ? (
                      <p className="mt-2 text-[11px] font-medium text-stone-500">
                        export: {item.metadata.file_name}
                      </p>
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </aside>
  );
}
