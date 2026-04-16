import { useState } from "react";
import { RefreshCw, AlertTriangle, ChevronRight, Layers } from "lucide-react";
import type {
  DecisionDiagnosticItem,
  DecisionDiagnosticSummary,
  DecisionGuidance,
  NextAction,
} from "../../lib/types";
import {
  AssistantVersionHistoryDialog,
  type AssistantReplyVersionItem,
} from "./assistant-version-history-dialog";
import { ActionOptions } from "./action-options";

export const DECISION_GUIDANCE_REASON_LABEL = "decision-guidance-reason";
const GUIDANCE_MODE_LABELS: Record<string, string> = {
  explore: "继续探索",
  narrow: "逐步收紧",
  compare: "对比选项",
  confirm: "开始确认",
};
const FOCUS_DIMENSION_LABELS: Record<string, string> = {
  target_user: "目标用户",
  problem: "核心问题",
  solution: "解决方案",
  boundary: "范围边界",
  constraint: "约束条件",
  validation: "验证标准",
};
const DIAGNOSTIC_TYPE_LABELS: Record<string, string> = {
  contradiction: "矛盾",
  gap: "缺口",
  assumption: "假设",
};

interface AssistantStatusBadge {
  hint?: string | null;
  label: string;
  tone: "active" | "success" | "warning" | "neutral";
}

interface AssistantTurnCardProps {
  canRegenerate?: boolean;
  collaborationModeLabel?: string | null;
  completedHint?: string | null;
  currentAction: NextAction | null;
  isFinalizeDisabled?: boolean;
  isFinalizing?: boolean;
  isRegenerating?: boolean;
  isWaiting?: boolean;
  latestAssistantMessage: string;
  onFinalize?: () => void;
  onRegenerate?: () => void;
  replyVersions?: AssistantReplyVersionItem[];
  showFinalizeAction?: boolean;
  statusBadge?: AssistantStatusBadge | null;
  showInterruptedMarker?: boolean;
  decisionGuidance?: DecisionGuidance | null;
  latestDiagnostics?: DecisionDiagnosticItem[];
  latestDiagnosticSummary?: DecisionDiagnosticSummary | null;
  onSelectDecisionGuidanceQuestion?: (question: string) => void;
  onRequestFreeSupplement?: () => void;
}

export function AssistantTurnCard({
  canRegenerate = false,
  collaborationModeLabel = null,
  completedHint = null,
  currentAction,
  isFinalizeDisabled = false,
  isFinalizing = false,
  isRegenerating = false,
  isWaiting = false,
  latestAssistantMessage,
  onFinalize,
  onRegenerate,
  replyVersions = [],
  showFinalizeAction = false,
  statusBadge = null,
  showInterruptedMarker = false,
  decisionGuidance = null,
  latestDiagnostics = [],
  latestDiagnosticSummary = null,
  onSelectDecisionGuidanceQuestion,
  onRequestFreeSupplement,
}: AssistantTurnCardProps) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const latestReplyVersion =
    replyVersions.find((version) => version.isLatest) ??
    replyVersions[replyVersions.length - 1] ??
    null;
  const [selectedHistoryVersionId, setSelectedHistoryVersionId] = useState<string | null>(
    latestReplyVersion?.assistantVersionId ?? null,
  );
  const confirmationReplies =
    decisionGuidance?.conversationStrategy === "confirm"
      ? decisionGuidance.confirmQuickReplies ?? []
      : [];
  const suggestionOptions = decisionGuidance?.suggestionOptions ?? [];
  const optionCards = decisionGuidance?.optionCards ?? [];
  const hasActionOptions =
    optionCards.length > 0 ||
    suggestionOptions.length > 0 ||
    Boolean(decisionGuidance?.freeformAffordance);
  const guidanceModeLabel = decisionGuidance?.guidanceMode
    ? GUIDANCE_MODE_LABELS[decisionGuidance.guidanceMode] ?? decisionGuidance.guidanceMode
    : null;
  const focusDimensionLabel = decisionGuidance?.focusDimension
    ? FOCUS_DIMENSION_LABELS[decisionGuidance.focusDimension] ?? decisionGuidance.focusDimension
    : null;
  const hasAnalysis = !!(
    currentAction?.observation ||
    currentAction?.challenge ||
    currentAction?.suggestion ||
    currentAction?.question
  );
  const badgeToneClassName = statusBadge?.tone === "success"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : statusBadge?.tone === "warning"
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : statusBadge?.tone === "neutral"
        ? "border-stone-200 bg-stone-100 text-stone-700"
        : "border-sky-200 bg-sky-50 text-sky-700";
  const badgeDotClassName = statusBadge?.tone === "success"
    ? "bg-emerald-500"
    : statusBadge?.tone === "warning"
      ? "bg-amber-500"
      : statusBadge?.tone === "neutral"
        ? "bg-stone-500"
        : "bg-sky-500";

  const openHistory = () => {
    setSelectedHistoryVersionId(latestReplyVersion?.assistantVersionId ?? null);
    setHistoryOpen(true);
  };

  return (
    <article className="rounded-2xl border border-stone-200/80 bg-white shadow-[0_2px_16px_rgba(0,0,0,0.05)]">
      <div className="flex items-center justify-between gap-4 border-b border-stone-100 px-6 py-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400">
            AI Co-founder
          </p>
          <h3 className="mt-1 text-base font-semibold text-stone-950">当前分析</h3>
          {statusBadge?.hint ? (
            <p className="mt-1 text-xs text-stone-500">{statusBadge.hint}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {showFinalizeAction ? (
            <button
              className="flex cursor-pointer items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 transition-all duration-150 hover:border-emerald-300 hover:bg-emerald-100 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40"
              disabled={isFinalizing || isFinalizeDisabled}
              onClick={onFinalize}
              type="button"
            >
              {isFinalizing ? "整理中..." : "生成最终版 PRD"}
            </button>
          ) : null}
          {replyVersions.length > 1 ? (
            <button
              className="flex cursor-pointer items-center gap-1.5 rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-stone-600 transition-all duration-150 hover:border-stone-900 hover:text-stone-950 active:scale-[0.97]"
              onClick={openHistory}
              type="button"
            >
              重新生成历史
            </button>
          ) : null}
          {canRegenerate ? (
            <button
              className="flex cursor-pointer items-center gap-1.5 rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-stone-600 transition-all duration-150 hover:border-stone-900 hover:text-stone-950 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40"
              disabled={isRegenerating}
              onClick={onRegenerate}
              type="button"
            >
              <RefreshCw className={`h-3 w-3 ${isRegenerating ? "animate-spin" : ""}`} />
              {isRegenerating ? "生成中..." : "重新生成"}
            </button>
          ) : null}
          {statusBadge ? (
            <div className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ${badgeToneClassName}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${badgeDotClassName}`} />
              {statusBadge.label}
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex flex-col gap-px p-5">
        <div className="rounded-xl bg-stone-50 p-4">
          <div className="flex items-center gap-2 border-b border-stone-100 pb-3">
            <Layers className="h-3.5 w-3.5 text-stone-400" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
              AI 回复
            </p>
          </div>
          {isWaiting || (!latestAssistantMessage && isRegenerating) ? (
            <div className="mt-3 flex items-center gap-2 py-1 text-sm text-stone-500">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 animate-pulse rounded-full bg-stone-300" style={{ animationDelay: "0ms" }} />
                <span className="h-2 w-2 animate-pulse rounded-full bg-stone-300" style={{ animationDelay: "150ms" }} />
                <span className="h-2 w-2 animate-pulse rounded-full bg-stone-300" style={{ animationDelay: "300ms" }} />
              </span>
              正在深度思考并组织回复...
            </div>
          ) : (
            <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-stone-800">
              {latestAssistantMessage || "正在思考并准备回复..."}
            </p>
          )}
          {showInterruptedMarker ? (
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              本轮已手动中断
            </div>
          ) : null}
        </div>
        {collaborationModeLabel ? (
          <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-600">
            <span className="font-medium text-stone-500">当前协作模式</span>
            <span className="font-semibold text-stone-900">{collaborationModeLabel}</span>
          </div>
        ) : null}
        {completedHint ? (
          <div className="mt-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {completedHint}
          </div>
        ) : null}

        {decisionGuidance ? (
          <div className="mt-2 rounded-xl border border-amber-100 bg-amber-50/50 p-4">
            <div className="flex items-center gap-2 border-b border-amber-100 pb-3">
              <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-amber-500">
                下一步建议
              </span>
            </div>
            <p className="mt-3 text-sm font-semibold text-stone-900">{decisionGuidance.strategyLabel}</p>
            {decisionGuidance.strategyReason ? (
              <p
                aria-label={DECISION_GUIDANCE_REASON_LABEL}
                className="mt-2 text-sm text-stone-700"
              >
                {decisionGuidance.strategyReason}
              </p>
            ) : null}
            {guidanceModeLabel || focusDimensionLabel ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {guidanceModeLabel ? (
                  <span className="rounded-full border border-amber-200 bg-white px-3 py-1 text-xs font-medium text-amber-700">
                    当前处于：{guidanceModeLabel}
                  </span>
                ) : null}
                {focusDimensionLabel ? (
                  <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-xs font-medium text-stone-700">
                    聚焦维度：{focusDimensionLabel}
                  </span>
                ) : null}
              </div>
            ) : null}
            {hasActionOptions ? (
              <div className="mt-3">
                <p className="mb-2 text-xs font-medium text-stone-500">可直接选择一个方向</p>
                <ActionOptions
                  freeformAffordance={decisionGuidance.freeformAffordance}
                  onRequestFreeSupplement={onRequestFreeSupplement}
                  onSelect={onSelectDecisionGuidanceQuestion}
                  optionCards={optionCards}
                  options={suggestionOptions}
                />
              </div>
            ) : null}
            {decisionGuidance.availableModeSwitches?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {decisionGuidance.availableModeSwitches.map((item) => (
                  <span
                    key={`${item.mode}-${item.label}`}
                    className="rounded-full border border-stone-200 bg-white px-3 py-1 text-xs text-stone-600"
                  >
                    你也可以切到：{item.label}
                  </span>
                ))}
              </div>
            ) : null}
            {confirmationReplies.length > 0 ? (
              <>
                <p className="mt-3 text-xs font-medium text-stone-500">确认后直接回复</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {confirmationReplies.map((reply) => (
                    <button
                      key={reply}
                      onClick={() => onSelectDecisionGuidanceQuestion?.(reply)}
                      type="button"
                      className="rounded-full border border-stone-200 bg-white px-3 py-1 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-100"
                    >
                      {reply}
                    </button>
                  ))}
                </div>
              </>
            ) : null}
            {!hasActionOptions ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {decisionGuidance.nextBestQuestions.map((question, index) => (
                  <button
                    key={`${index}-${question}`}
                    onClick={() => onSelectDecisionGuidanceQuestion?.(question)}
                    type="button"
                    className="rounded-full border border-amber-200 bg-white px-3 py-1 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100"
                  >
                    {question}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {latestDiagnostics.length > 0 ? (
          <div className="mt-2 rounded-xl border border-rose-100 bg-rose-50/60 p-4">
            <div className="flex items-center justify-between gap-3 border-b border-rose-100 pb-3">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-rose-500">
                  本轮诊断
                </span>
                <p className="mt-1 text-sm font-semibold text-stone-900">这轮暴露出的关键问题</p>
              </div>
              {latestDiagnosticSummary ? (
                <span className="rounded-full border border-rose-200 bg-white px-3 py-1 text-xs text-rose-600">
                  open {latestDiagnosticSummary.openCount}
                </span>
              ) : null}
            </div>
            <div className="mt-4 flex flex-col gap-3">
              {latestDiagnostics.slice(0, 3).map((item) => (
                <article key={item.id} className="rounded-xl border border-rose-100 bg-white p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] font-medium text-rose-700">
                      {DIAGNOSTIC_TYPE_LABELS[item.type] ?? item.type}
                    </span>
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
                  <p className="mt-2 text-xs font-medium text-stone-700">
                    下一步：{item.suggestedNextStep.label}
                  </p>
                </article>
              ))}
            </div>
          </div>
        ) : null}

        {hasAnalysis && showAnalysis ? (
          <>
            {currentAction?.observation ? (
              <div className="mt-2 rounded-xl bg-stone-50 p-4">
                <p className="border-b border-stone-100 pb-3 text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
                  我的判断
                </p>
                <p className="mt-3 text-sm leading-7 text-stone-700">
                  {currentAction.observation}
                </p>
              </div>
            ) : null}

            {currentAction?.challenge ? (
              <div className="mt-2 rounded-xl border border-red-100 bg-red-50/60 p-4">
                <div className="flex items-center gap-2 border-b border-red-100 pb-3">
                  <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
                  <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-red-500">
                    风险 / 不确定点
                  </p>
                </div>
                <p className="mt-3 text-sm leading-7 text-red-700">
                  {currentAction.challenge}
                </p>
              </div>
            ) : null}

            {currentAction?.suggestion ? (
              <div className="mt-2 rounded-xl bg-stone-50 p-4">
                <p className="border-b border-stone-100 pb-3 text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
                  PM 建议
                </p>
                <p className="mt-3 text-sm leading-7 text-stone-700">
                  {currentAction.suggestion}
                </p>
              </div>
            ) : null}

            {currentAction?.question ? (
              <div className="mt-2 rounded-xl bg-stone-950 p-4">
                <div className="flex items-center gap-2 border-b border-stone-800 pb-3">
                  <ChevronRight className="h-3.5 w-3.5 text-stone-400" />
                  <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
                    下一步
                  </p>
                </div>
                <p className="mt-3 text-sm leading-7 text-stone-100">{currentAction.question}</p>
              </div>
            ) : null}

            <button
              onClick={() => setShowAnalysis(false)}
              className="mt-2 flex w-full cursor-pointer items-center justify-center rounded-xl border border-dashed border-stone-200 bg-stone-50 py-2.5 text-xs text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-800"
            >
              收起深度分析
            </button>
          </>
        ) : hasAnalysis ? (
          <button
            onClick={() => setShowAnalysis(true)}
            className="mt-2 flex w-full cursor-pointer items-center justify-center rounded-xl border border-dashed border-stone-200 bg-stone-50/50 py-2.5 text-xs text-stone-500 transition-colors hover:bg-stone-50 hover:text-stone-800"
          >
            展开 AI 深度分析及推理
          </button>
        ) : null}
      </div>
      <AssistantVersionHistoryDialog
        onClose={() => setHistoryOpen(false)}
        onSelectVersion={setSelectedHistoryVersionId}
        open={historyOpen}
        selectedVersionId={selectedHistoryVersionId}
        versions={replyVersions}
      />
    </article>
  );
}
