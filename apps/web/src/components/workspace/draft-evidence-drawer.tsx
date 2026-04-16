"use client";

import type { FirstDraftEvidenceItem } from "../../lib/types";

interface DraftEvidenceDrawerProps {
  item: FirstDraftEvidenceItem | null;
  onClose: () => void;
}

const KIND_LABELS: Record<FirstDraftEvidenceItem["kind"], string> = {
  user_message: "用户原话",
  assistant_decision: "助手决策",
  system_inference: "系统推断",
  diagnostic: "诊断项",
};

export function DraftEvidenceDrawer({ item, onClose }: DraftEvidenceDrawerProps) {
  if (!item) {
    return null;
  }

  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-amber-600">
            Evidence
          </p>
          <h4 className="mt-1 text-sm font-semibold text-stone-950">来源追溯</h4>
        </div>
        <button
          className="rounded-lg border border-amber-200 bg-white px-2.5 py-1 text-xs text-stone-600"
          onClick={onClose}
          type="button"
        >
          关闭
        </button>
      </div>
      <div className="mt-3 space-y-2 text-xs text-stone-700">
        <p>类型：{KIND_LABELS[item.kind]}</p>
        <p>关联章节：{item.sectionKeys.join(" / ")}</p>
        <div className="rounded-lg border border-amber-100 bg-white px-3 py-2 text-sm leading-6 text-stone-800">
          {item.excerpt}
        </div>
      </div>
    </section>
  );
}
