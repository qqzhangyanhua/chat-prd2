"use client";

import { useState } from "react";

import type { FirstDraftEvidenceItem, FirstDraftState } from "../../lib/types";
import { DraftEvidenceDrawer } from "./draft-evidence-drawer";

interface FirstDraftCardProps {
  firstDraft: FirstDraftState;
}

const STATUS_LABELS = {
  confirmed: "已确认",
  inferred: "推断",
  to_validate: "待验证",
} as const;

const STATUS_CLASSNAMES = {
  confirmed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  inferred: "border-stone-200 bg-stone-100 text-stone-700",
  to_validate: "border-amber-200 bg-amber-50 text-amber-700",
} as const;

export function FirstDraftCard({ firstDraft }: FirstDraftCardProps) {
  const [activeEvidence, setActiveEvidence] = useState<FirstDraftEvidenceItem | null>(null);

  const sections = Object.entries(firstDraft.sections);
  if (!sections.length) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-stone-200/80 bg-white p-5 shadow-[0_2px_12px_rgba(0,0,0,0.04)]">
      <div className="flex items-center justify-between gap-3 border-b border-stone-100 pb-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
            First Draft
          </p>
          <h3 className="mt-1 text-sm font-semibold text-stone-950">结构化首稿</h3>
        </div>
        {firstDraft.latestUpdates.entryIds.length ? (
          <div className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs text-stone-600">
            {firstDraft.latestUpdates.entryIds.length} 条新增
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-col gap-4">
        {sections.map(([sectionKey, section]) => (
          <article key={sectionKey} className="rounded-xl border border-stone-200 bg-stone-50/70 p-4">
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-sm font-semibold text-stone-900">{section.title}</h4>
              <span className="text-[11px] text-stone-500">{section.completeness}</span>
            </div>
            <div className="mt-3 flex flex-col gap-3">
              {section.entries.map((entry) => (
                <div key={entry.id} className="rounded-xl border border-stone-200 bg-white p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span
                      className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${STATUS_CLASSNAMES[entry.assertionState]}`}
                    >
                      {STATUS_LABELS[entry.assertionState]}
                    </span>
                    {entry.evidenceRefIds.length ? (
                      <button
                        className="rounded-lg border border-stone-200 bg-stone-50 px-2.5 py-1 text-xs text-stone-600 hover:bg-stone-100"
                        onClick={() => {
                          setActiveEvidence(firstDraft.evidenceRegistry[entry.evidenceRefIds[0]] ?? null);
                        }}
                        type="button"
                      >
                        查看来源
                      </button>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-stone-800">{entry.text}</p>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className="mt-4">
        <DraftEvidenceDrawer
          item={activeEvidence}
          onClose={() => {
            setActiveEvidence(null);
          }}
        />
      </div>
    </section>
  );
}
