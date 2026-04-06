"use client";

import { FileText } from "lucide-react";
import { useWorkspaceStore } from "../../store/workspace-store";
import { PrdSectionCard } from "./prd-section-card";


const sectionOrder = ["target_user", "problem", "solution", "mvp_scope"];


export function PrdPanel() {
  const sections = useWorkspaceStore((state) => state.prd.sections);

  const confirmedCount = sectionOrder
    .map((key) => sections[key])
    .filter((s) => s?.status === "confirmed").length;

  return (
    <aside className="flex h-full w-[360px] shrink-0 flex-col rounded-2xl border border-stone-200/80 bg-white/90 p-4 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-stone-100 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-stone-200 bg-stone-100">
            <FileText className="h-3.5 w-3.5 text-stone-500" />
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400">
              Live Snapshot
            </p>
            <h2 className="mt-0.5 text-sm font-semibold text-stone-950">PRD</h2>
          </div>
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-stone-200 bg-stone-50 px-2.5 py-1 text-[10px] font-medium text-stone-500">
          <span className="font-semibold text-stone-700">{confirmedCount}</span>
          <span>/</span>
          <span>{sectionOrder.length}</span>
          <span>已确认</span>
        </div>
      </div>

      <p className="mt-3 text-xs leading-5 text-stone-400">
        下方不是终稿，而是目前被确认下来的产品共识。
      </p>

      <div className="mt-4 flex flex-col gap-2">
        {sectionOrder
          .map((key) => sections[key])
          .filter(Boolean)
          .map((section) => (
            <PrdSectionCard
              key={section.title}
              description={section.content}
              status={section.status}
              title={section.title}
            />
          ))}

        {sectionOrder.filter((key) => !sections[key]).length > 0 ? (
          <div className="flex flex-col gap-1.5">
            {sectionOrder
              .filter((key) => !sections[key])
              .map((key) => (
                <div
                  key={key}
                  className="rounded-xl border border-dashed border-stone-200 px-4 py-3 text-xs text-stone-400"
                >
                  {key === "target_user" && "目标用户 — 待确认"}
                  {key === "problem" && "核心问题 — 待确认"}
                  {key === "solution" && "解决方案 — 待确认"}
                  {key === "mvp_scope" && "MVP 范围 — 待确认"}
                </div>
              ))}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
