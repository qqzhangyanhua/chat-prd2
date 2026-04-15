"use client";

import { FileText } from "lucide-react";
import { finalizeSession } from "../../lib/api";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { useWorkspaceStore, workspaceStore } from "../../store/workspace-store";
import { PrdSectionCard } from "./prd-section-card";


const sectionOrder = ["target_user", "problem", "solution", "mvp_scope"];
const finalizedExtraSectionOrder = ["constraints", "success_metrics", "out_of_scope", "open_questions"];
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
  const extraSections = useWorkspaceStore((state) => state.prd.extraSections);
  const isCompleted = useWorkspaceStore((state) => state.isCompleted);
  const isFinalizing = useWorkspaceStore((state) => state.isFinalizingSession);
  const isFinalizeReady = useWorkspaceStore((state) => state.isFinalizeReady);
  const isStreaming = useWorkspaceStore((state) => state.isStreaming);
  const meta = useWorkspaceStore((state) => state.prd.meta);
  const sections = useWorkspaceStore((state) => state.prd.sections);
  const canFinalize = meta.stageTone === "ready" && isFinalizeReady && !isCompleted;
  const isFinalizeDisabled = isFinalizing || isStreaming;

  const stageHintMessage =
    meta.stageTone === "final"
      ? "已生成最终版 PRD，后续补充会基于终稿继续迭代。"
      : canFinalize
        ? "当前已满足终稿整理条件，你可以直接生成最终版 PRD。"
        : "下方不是终稿，而是目前被确认下来的产品共识。";

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

  const confirmedCount = sectionOrder
    .map((key) => sections[key])
    .filter((s) => s?.status === "confirmed").length;
  const orderedExtraSections =
    meta.stageTone === "final"
      ? finalizedExtraSectionOrder
          .map((key) => [key, extraSections[key]] as const)
          .filter((entry): entry is readonly [string, NonNullable<typeof extraSections[string]>] => Boolean(entry[1]))
      : Object.entries(extraSections);

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
        <div className="flex flex-col items-end gap-1.5">
          <div
            className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${stageToneClassMap[meta.stageTone]}`}
          >
            {meta.stageLabel}
          </div>
          <div className="flex items-center gap-1.5 rounded-full border border-stone-200 bg-stone-50 px-2.5 py-1 text-[10px] font-medium text-stone-500">
            <span className="font-semibold text-stone-700">{confirmedCount}</span>
            <span>/</span>
            <span>{sectionOrder.length}</span>
            <span>已确认</span>
          </div>
        </div>
      </div>

      <p className="mt-3 text-xs leading-5 text-stone-400">{stageHintMessage}</p>
      {canFinalize ? (
        <button
          className="mt-3 inline-flex w-full cursor-pointer items-center justify-center rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isFinalizeDisabled}
          onClick={handleFinalize}
          type="button"
        >
          {isFinalizing ? "整理中..." : "生成最终版 PRD"}
        </button>
      ) : null}
      <div className="mt-3 rounded-xl border border-stone-200/80 bg-stone-50 px-3 py-2">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">
            Critic
          </p>
          {meta.draftVersion ? (
            <span className="text-[11px] font-medium text-stone-500">PRD v{meta.draftVersion}</span>
          ) : null}
        </div>
        <p className="mt-1 text-xs leading-5 text-stone-600">{meta.criticSummary}</p>
        {meta.criticGaps.length > 0 ? (
          <ul className="mt-2 flex flex-col gap-1 text-xs leading-5 text-stone-600">
            {meta.criticGaps.map((gap) => (
              <li key={gap} className="rounded-lg bg-white/80 px-2 py-1">
                {gap}
              </li>
            ))}
          </ul>
        ) : null}
        {meta.nextQuestion ? (
          <div className="mt-2 rounded-lg border border-dashed border-stone-200 bg-white/70 px-2 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">
              当前唯一下一问
            </p>
            <p className="mt-1 text-xs leading-5 text-stone-600">{meta.nextQuestion}</p>
          </div>
        ) : null}
      </div>

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

        {orderedExtraSections.length > 0 ? (
          <div className="mt-2 flex flex-col gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">
              草稿补充
            </p>
            {orderedExtraSections.map(([key, section]) => (
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
