"use client";

import { FileText, Sparkles } from "lucide-react";
import { finalizeSession } from "../../lib/api";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { useWorkspaceStore, workspaceStore } from "../../store/workspace-store";
import { PrdSectionCard } from "./prd-section-card";

const primarySectionOrder = [
  "target_user",
  "problem",
  "solution",
  "mvp_scope",
  "constraints",
  "success_metrics",
] as const;
const auxiliarySectionOrder = ["risks_to_validate", "open_questions"] as const;
const stageToneClassMap = {
  draft: "border-stone-200 bg-stone-50 text-stone-600",
  ready: "border-amber-200 bg-amber-50 text-amber-700",
  final: "border-emerald-200 bg-emerald-50 text-emerald-700",
} as const;

interface PrdPanelProps {
  sessionId: string;
}

export function PrdPanel({ sessionId }: PrdPanelProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);
  const isCompleted = useWorkspaceStore((state) => state.isCompleted);
  const isFinalizing = useWorkspaceStore((state) => state.isFinalizingSession);
  const isFinalizeReady = useWorkspaceStore((state) => state.isFinalizeReady);
  const isStreaming = useWorkspaceStore((state) => state.isStreaming);
  const prd = useWorkspaceStore((state) => state.prd);
  const prdReview = useWorkspaceStore((state) => state.prdReview);
  const canConfirmDraft = prd.readyForConfirmation && isFinalizeReady && !isCompleted;
  const canFinalizeLegacy =
    !prd.readyForConfirmation && isFinalizeReady && prd.meta.stageTone === "ready" && !isCompleted;
  const canFinalize = canConfirmDraft || canFinalizeLegacy;
  const isFinalizeDisabled = isFinalizing || isStreaming;
  const finalizeButtonLabel = canConfirmDraft ? "确认初稿并生成最终版 PRD" : "生成最终版 PRD";

  const stageHintMessage =
    prd.meta.stageTone === "final"
      ? "当前已经进入稳定终稿视图，后续补充会基于终稿继续增量更新。"
      : canConfirmDraft
        ? "可以先确认当前 PRD 初稿，再生成最终版。"
        : canFinalizeLegacy
          ? "当前已满足终稿整理条件，你可以直接生成最终版 PRD。"
        : "右侧会持续展示当前 PRD 收敛结果，并明确提示还需要继续补哪些章节。";

  async function handleFinalize() {
    if (
      !sessionId ||
      workspaceStore.getState().isFinalizingSession ||
      workspaceStore.getState().isStreaming
    ) {
      return;
    }

    workspaceStore.getState().setSessionFinalizing(true);
    try {
      const snapshot = await finalizeSession(
        sessionId,
        { confirmation_source: "button" },
        accessToken,
      );
      workspaceStore.getState().refreshSessionSnapshot(snapshot);
      showToast({
        id: `session-finalize-${sessionId}`,
        message: "已生成最终版 PRD。",
        tone: "success",
      });
    } catch (error) {
      console.error("整理最终版 PRD 失败", error);
      showToast({
        id: `session-finalize-${sessionId}`,
        message: "生成最终版 PRD 失败，请稍后重试。",
        tone: "error",
      });
    } finally {
      workspaceStore.getState().setSessionFinalizing(false);
    }
  }

  const confirmedCount = primarySectionOrder
    .map((key) => prd.sections[key])
    .filter((section) => section?.status === "confirmed").length;
  const primarySections = primarySectionOrder
    .map((key) => [key, prd.sections[key]] as const)
    .filter((entry): entry is readonly [string, NonNullable<typeof prd.sections[string]>] => Boolean(entry[1]));
  const auxiliarySections = auxiliarySectionOrder
    .map((key) => [key, prd.sections[key]] as const)
    .filter((entry): entry is readonly [string, NonNullable<typeof prd.sections[string]>] => {
      return Boolean(entry[1]?.content?.trim());
    });
  const legacySupplementalSections = Object.entries(prd.sections).filter(
    ([key, section]) =>
      !primarySectionOrder.includes(key as (typeof primarySectionOrder)[number]) &&
      !auxiliarySectionOrder.includes(key as (typeof auxiliarySectionOrder)[number]) &&
      Boolean(section?.content?.trim()),
  );

  return (
    <aside className="flex w-full flex-col rounded-2xl border border-stone-200/80 bg-white/90 p-4 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
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
        <div className="flex flex-col items-end gap-1.5">
          <div
            className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${stageToneClassMap[prd.meta.stageTone]}`}
          >
            {prd.meta.stageLabel}
          </div>
          <div className="flex items-center gap-1.5 rounded-full border border-stone-200 bg-stone-50 px-2.5 py-1 text-[10px] font-medium text-stone-500">
            <span className="font-semibold text-stone-700">{confirmedCount}</span>
            <span>/</span>
            <span>{primarySectionOrder.length}</span>
            <span>已确认</span>
          </div>
        </div>
      </div>

      <p className="mt-3 text-xs leading-5 text-stone-500">{stageHintMessage}</p>
      {canFinalize ? (
        <button
          className="mt-3 inline-flex w-full cursor-pointer items-center justify-center rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isFinalizeDisabled}
          onClick={handleFinalize}
          type="button"
        >
          {isFinalizing ? "整理中..." : finalizeButtonLabel}
        </button>
      ) : null}

      <div className="mt-3 rounded-xl border border-stone-200/80 bg-stone-50 px-3 py-2">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">
            收敛状态
          </p>
          {prd.meta.draftVersion ? (
            <span className="text-[11px] font-medium text-stone-500">PRD v{prd.meta.draftVersion}</span>
          ) : null}
        </div>
        <p className="mt-1 text-xs leading-5 text-stone-600">{prd.meta.criticSummary}</p>
        {prd.meta.criticGaps.length > 0 ? (
          <ul className="mt-2 flex flex-col gap-1 text-xs leading-5 text-stone-600">
            {prd.meta.criticGaps.map((gap) => (
              <li key={gap} className="rounded-lg bg-white/80 px-2 py-1">
                {gap}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {prdReview ? (
        <div
          className="mt-3 rounded-xl border border-sky-200 bg-sky-50/80 px-3 py-3"
          data-testid="prd-review-summary"
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-700">质量复核</p>
            <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-sky-700">
              {prdReview.verdict}
            </span>
          </div>
          <p className="mt-2 text-xs leading-5 text-sky-900">{prdReview.summary}</p>
          {prdReview.gaps.length > 0 ? (
            <ul className="mt-2 flex flex-col gap-1 text-xs leading-5 text-sky-900">
              {prdReview.gaps.slice(0, 3).map((gap) => (
                <li key={gap} className="rounded-lg bg-white/80 px-2 py-1">{gap}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {prd.gapPrompts.length > 0 ? (
        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-3">
          <div className="flex items-center gap-2 text-amber-800">
            <Sparkles className="h-4 w-4" />
            <p className="text-xs font-semibold">继续补这 {prd.gapPrompts.length} 项</p>
          </div>
          <ul className="mt-2 flex flex-col gap-1.5 text-xs leading-5 text-amber-900">
            {prd.gapPrompts.map((prompt) => (
              <li key={prompt} className="rounded-lg bg-white/70 px-2 py-1">
                {prompt}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-4 flex flex-col gap-2 overflow-y-auto pr-1">
        <div className="flex flex-col gap-2">
          {primarySections.map(([key, section]) => {
            const isChanged = prd.sectionsChanged.includes(key);
            const isMissing = prd.missingSections.includes(key);
            return (
              <div key={key} className={`rounded-2xl ${isChanged ? "bg-amber-50/80 p-1" : ""}`}>
                {isChanged ? (
                  <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">
                    本轮更新
                  </p>
                ) : null}
                <PrdSectionCard
                  description={
                    isMissing && !section.content.trim()
                      ? "这一章还没有可展示内容，继续补齐后会出现在这里。"
                      : section.content
                  }
                  status={isMissing && !section.content.trim() ? "missing" : section.status}
                  title={section.title}
                />
              </div>
            );
          })}
        </div>

        {auxiliarySections.length > 0 ? (
          <div className="mt-2 flex flex-col gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">
              辅助章节
            </p>
            {auxiliarySections.map(([key, section]) => {
              const isChanged = prd.sectionsChanged.includes(key);
              return (
                <div key={key} className={`rounded-2xl ${isChanged ? "bg-amber-50/80 p-1" : ""}`}>
                  {isChanged ? (
                    <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">
                      本轮更新
                    </p>
                  ) : null}
                  <PrdSectionCard
                    description={section.content}
                    status={section.status}
                    title={section.title}
                  />
                </div>
              );
            })}
          </div>
        ) : null}

        {legacySupplementalSections.length > 0 ? (
          <div className="mt-2 flex flex-col gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">
              草稿补充
            </p>
            {legacySupplementalSections.map(([key, section]) => (
              <PrdSectionCard
                key={key}
                description={section.content}
                status={section.status}
                title={section.title}
              />
            ))}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
