"use client";

import { useWorkspaceStore } from "../../store/workspace-store";
import { PrdSectionCard } from "./prd-section-card";


const sectionOrder = ["target_user", "problem", "solution", "mvp_scope"];


export function PrdPanel() {
  const sections = useWorkspaceStore((state) => state.prd.sections);

  return (
    <aside className="flex h-full flex-col rounded-[28px] border border-stone-200 bg-stone-50 p-5 shadow-sm">
      <div className="border-b border-stone-200 pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">
          Live Snapshot
        </p>
        <h2 className="mt-2 text-2xl font-semibold text-stone-950">PRD</h2>
        <p className="mt-2 text-sm leading-6 text-stone-600">
          右侧不是文档终稿，而是当前被确认下来的产品共识。
        </p>
      </div>

      <div className="mt-5 space-y-3">
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
      </div>
    </aside>
  );
}
