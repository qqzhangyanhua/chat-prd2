import { useState } from "react";
import { RefreshCw, AlertTriangle, ChevronRight, Layers } from "lucide-react";
import type { NextAction } from "../../lib/types";
import { workspaceStore } from "../../store/workspace-store";
import { ActionOptions } from "./action-options";
import {
  AssistantVersionHistoryDialog,
  type AssistantReplyVersionItem,
} from "./assistant-version-history-dialog";

interface AssistantTurnCardProps {
  canRegenerate?: boolean;
  currentAction: NextAction | null;
  isRegenerating?: boolean;
  latestAssistantMessage: string;
  onRegenerate?: () => void;
  replyVersions?: AssistantReplyVersionItem[];
  showInterruptedMarker?: boolean;
}

const defaultOptions = [
  "先继续确认目标用户是谁，再决定切入场景。",
  "先把最痛的问题讲清楚，再判断方案是否成立。",
  "先把 MVP 范围压小，只保留第一版必须成立的能力。",
];

export function AssistantTurnCard({
  canRegenerate = false,
  currentAction,
  isRegenerating = false,
  latestAssistantMessage,
  onRegenerate,
  replyVersions = [],
  showInterruptedMarker = false,
}: AssistantTurnCardProps) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const latestReplyVersion =
    replyVersions.find((version) => version.isLatest) ??
    replyVersions[replyVersions.length - 1] ??
    null;
  const [selectedHistoryVersionId, setSelectedHistoryVersionId] = useState<string | null>(
    latestReplyVersion?.assistantVersionId ?? null,
  );
  const nextQuestion =
    currentAction?.target === "target_user"
      ? "你现在最想服务的第一类用户是谁？请尽量具体到角色、场景和触发时机。"
      : "如果只能先做一个最小版本，你希望它优先解决哪一个关键问题？";

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
        </div>
        <div className="flex items-center gap-2">
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
          <div className="flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            持续引导中
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-px p-5">
        <div className="rounded-xl bg-stone-50 p-4">
          <div className="flex items-center gap-2 border-b border-stone-100 pb-3">
            <Layers className="h-3.5 w-3.5 text-stone-400" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
              我当前的理解
            </p>
          </div>
          <p className="mt-3 text-sm leading-7 text-stone-700">
            {latestAssistantMessage || "我会先根据你刚提供的信息整理理解，再继续追问关键缺口。"}
          </p>
          {showInterruptedMarker ? (
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              本轮已手动中断
            </div>
          ) : null}
        </div>

        <div className="mt-2 rounded-xl bg-stone-50 p-4">
          <p className="border-b border-stone-100 pb-3 text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
            我的判断
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-700">
            {currentAction?.reason ?? "我会继续找出还没被说透的前提、目标和决策点。"}
          </p>
        </div>

        <div className="mt-2 rounded-xl border border-red-100 bg-red-50/60 p-4">
          <div className="flex items-center gap-2 border-b border-red-100 pb-3">
            <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-red-500">
              风险 / 不确定点
            </p>
          </div>
          <p className="mt-3 text-sm leading-7 text-red-700">
            如果目标用户、核心问题和第一版边界都还模糊，方案很容易看起来完整，但落地时失焦。
          </p>
        </div>

        <div className="mt-2 rounded-xl bg-stone-50 p-4">
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
            可选推进方式
          </p>
          <ActionOptions
            onSelect={(option) => workspaceStore.getState().setInputValue(option)}
            options={defaultOptions}
          />
        </div>

        <div className="mt-2 rounded-xl bg-stone-950 p-4">
          <div className="flex items-center gap-2 border-b border-stone-800 pb-3">
            <ChevronRight className="h-3.5 w-3.5 text-stone-400" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
              下一步
            </p>
          </div>
          <p className="mt-3 text-sm leading-7 text-stone-100">{nextQuestion}</p>
        </div>
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
