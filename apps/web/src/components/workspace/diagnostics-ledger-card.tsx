"use client";

import type { DecisionDiagnosticSummary, DiagnosticLedgerGroup } from "../../lib/types";

const BUCKET_EMPTY_LABELS: Record<string, string> = {
  unknown: "当前无此类问题",
  risk: "当前无此类问题",
  to_validate: "当前无此类问题",
};

interface DiagnosticsLedgerCardProps {
  groups: DiagnosticLedgerGroup[];
  summary?: DecisionDiagnosticSummary | null;
}

export function DiagnosticsLedgerCard({ groups, summary }: DiagnosticsLedgerCardProps) {
  return (
    <section className="rounded-2xl border border-stone-200/80 bg-white p-5 shadow-[0_2px_12px_rgba(0,0,0,0.04)]">
      <div className="flex items-center justify-between gap-3 border-b border-stone-100 pb-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
            持续问题台账
          </p>
          <h3 className="mt-1 text-sm font-semibold text-stone-950">当前还没压实的问题</h3>
        </div>
        <div className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs text-stone-600">
          open {summary?.openCount ?? groups.reduce((count, group) => count + group.items.length, 0)}
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {groups.map((group) => (
          <section key={group.bucket} className="rounded-xl border border-stone-200 bg-stone-50/70 p-4">
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-stone-900">{group.label}</h4>
              <span className="rounded-full bg-white px-2.5 py-1 text-xs text-stone-500">
                {group.items.length}
              </span>
            </div>
            {group.items.length === 0 ? (
              <p className="mt-3 text-xs leading-6 text-stone-500">{BUCKET_EMPTY_LABELS[group.bucket]}</p>
            ) : (
              <div className="mt-3 flex flex-col gap-3">
                {group.items.map((item) => (
                  <article key={item.id} className="rounded-xl border border-stone-200 bg-white p-3">
                    <div className="flex flex-wrap gap-2">
                      {item.impactScope.map((scope) => (
                        <span
                          key={`${item.id}-${scope}`}
                          className="rounded-full border border-stone-200 px-2.5 py-1 text-[11px] text-stone-600"
                        >
                          {scope}
                        </span>
                      ))}
                    </div>
                    <p className="mt-2 text-sm font-semibold text-stone-900">{item.title}</p>
                    <p className="mt-1 text-xs leading-6 text-stone-600">{item.detail}</p>
                    <div className="mt-3 rounded-lg bg-stone-50 px-3 py-2">
                      <p className="text-[11px] font-medium text-stone-500">建议下一步</p>
                      <p className="mt-1 text-xs leading-6 text-stone-700">
                        {item.suggestedNextStep.prompt}
                      </p>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        ))}
      </div>
    </section>
  );
}
