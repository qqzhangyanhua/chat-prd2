import type { NextAction } from "../../lib/types";
import { ActionOptions } from "./action-options";

interface AssistantTurnCardProps {
  currentAction: NextAction | null;
  latestAssistantMessage: string;
  showInterruptedMarker?: boolean;
}

const defaultOptions = [
  "继续追问早期创业者",
  "收窄到独立开发者",
  "直接定义第一个 MVP 人群",
];

export function AssistantTurnCard({
  currentAction,
  latestAssistantMessage,
  showInterruptedMarker = false,
}: AssistantTurnCardProps) {
  const nextQuestion =
    currentAction?.target === "target_user"
      ? "这一轮先把目标用户收窄一层：是刚开始做产品的独立开发者，还是已经有用户但增长停滞的团队？"
      : "你希望这一轮先推进用户画像、问题定义，还是 MVP 范围？";

  return (
    <article className="rounded-[28px] border border-stone-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-stone-200 pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">
            AI Co-founder
          </p>
          <h3 className="mt-2 text-2xl font-semibold text-stone-950">对话推进</h3>
        </div>
        <div className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
          当前阶段：验证需求
        </div>
      </div>

      <div className="mt-6 grid gap-4">
        <section className="rounded-2xl bg-stone-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
            理解
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-700">
            {latestAssistantMessage || "先把目标用户讲清楚，再继续往下收敛 MVP。"}
          </p>
          {showInterruptedMarker ? (
            <div className="mt-3 inline-flex rounded-full border border-amber-200 bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              本轮已手动中断
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl bg-stone-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
            判断
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-700">
            {currentAction?.reason ?? "当前还需要继续追问，先避免把范围扩到过大的用户群。"}
          </p>
        </section>

        <section className="rounded-2xl border border-red-200 bg-red-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-red-600">
            风险
          </p>
          <p className="mt-3 text-sm leading-7 text-red-700">
            “所有创业者都需要” 这种说法太宽，会让产品看起来什么都能做，最后什么都不够深。
          </p>
        </section>

        <section className="space-y-3 rounded-2xl bg-stone-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
            可选方案
          </p>
          <ActionOptions options={defaultOptions} />
        </section>

        <section className="rounded-2xl border border-stone-200 bg-stone-950 p-4 text-white">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-300">
            下一步问题
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-100">{nextQuestion}</p>
        </section>
      </div>
    </article>
  );
}
