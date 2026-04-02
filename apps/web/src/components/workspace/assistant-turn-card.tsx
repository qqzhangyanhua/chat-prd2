import { ActionOptions } from "./action-options";


export function AssistantTurnCard() {
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
            你现在想做的是一个能陪用户反复梳理产品方向的智能体，而不是一次性写完文档的 PRD 生成器。
          </p>
        </section>

        <section className="rounded-2xl bg-stone-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
            判断
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-700">
            如果目标用户仍然太宽，后面的功能、场景和 MVP 都会继续发散，所以这轮应该优先收窄用户画像。
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
          <ActionOptions />
        </section>

        <section className="rounded-2xl border border-stone-200 bg-stone-950 p-4 text-white">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-300">
            下一步问题
          </p>
          <p className="mt-3 text-sm leading-7 text-stone-100">
            你最想先服务的是哪一类人: 第一次做产品的创业者，还是已经在做产品但方向模糊的独立开发者？
          </p>
        </section>
      </div>
    </article>
  );
}
