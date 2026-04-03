import type { NextAction } from "../../lib/types";
import { ActionOptions } from "./action-options";

interface AssistantTurnCardProps {
  canRegenerate?: boolean;
  currentAction: NextAction | null;
  isRegenerating?: boolean;
  latestAssistantMessage: string;
  onRegenerate?: () => void;
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
  showInterruptedMarker = false,
}: AssistantTurnCardProps) {
  const nextQuestion =
    currentAction?.target === "target_user"
      ? "你现在最想服务的第一类用户是谁？请尽量具体到角色、场景和触发时机。"
      : "如果只能先做一个最小版本，你希望它优先解决哪一个关键问题？";

  return (
    <article className="rounded-[28px] border border-stone-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-stone-200 pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">
            AI Co-founder
          </p>
          <h3 className="mt-2 text-2xl font-semibold text-stone-950">当前分析</h3>
        </div>
        <div className="flex items-center gap-3">
          {canRegenerate ? (
            <button
              className="rounded-full border border-stone-300 bg-white px-3 py-1 text-xs font-medium text-stone-700 transition hover:border-stone-900 hover:text-stone-950 disabled:cursor-not-allowed disabled:border-stone-200 disabled:bg-stone-100 disabled:text-stone-400"
              disabled={isRegenerating}
              onClick={onRegenerate}
              type="button"
            >
              {isRegenerating ? "重新生成中..." : "重新生成"}
            </button>
          ) : null}
          <div className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
            持续引导中
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-4">
        <section className="rounded-2xl bg-stone-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
            我当前的理解
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-700">
            {latestAssistantMessage || "我会先根据你刚提供的信息整理理解，再继续追问关键缺口。"}
          </p>
          {showInterruptedMarker ? (
            <div className="mt-3 inline-flex rounded-full border border-amber-200 bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              本轮已手动中断
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl bg-stone-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
            我的判断
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-700">
            {currentAction?.reason ?? "我会继续找出还没被说透的前提、目标和决策点。"}
          </p>
        </section>

        <section className="rounded-2xl border border-red-200 bg-red-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-red-600">
            风险 / 不确定点
          </p>
          <p className="mt-3 text-sm leading-7 text-red-700">
            如果目标用户、核心问题和第一版边界都还模糊，方案很容易看起来完整，但落地时失焦。
          </p>
        </section>

        <section className="space-y-3 rounded-2xl bg-stone-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
            可选推进方式
          </p>
          <ActionOptions options={defaultOptions} />
        </section>

        <section className="rounded-2xl border border-stone-200 bg-stone-950 p-4 text-white">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-300">
            下一步
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-100">{nextQuestion}</p>
        </section>
      </div>
    </article>
  );
}
