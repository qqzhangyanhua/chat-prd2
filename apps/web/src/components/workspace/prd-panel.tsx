import { PrdSectionCard } from "./prd-section-card";


export function PrdPanel() {
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
        <PrdSectionCard
          description="已经聚焦到方向模糊、需要被追问和收敛的独立开发者。"
          status="confirmed"
          title="目标用户"
        />
        <PrdSectionCard
          description="他们往往能描述很多想法，但说不清核心问题、用户和优先级。"
          status="inferred"
          title="核心问题"
        />
        <PrdSectionCard
          description="通过结构化提问、挑战和选项推进，把模糊想法收敛成可执行 PRD。"
          status="inferred"
          title="解决方案"
        />
        <PrdSectionCard
          description="还没有正式框定 MVP，只能先看出会围绕对话、决策与 PRD 面板。"
          status="missing"
          title="MVP 范围"
        />
      </div>
    </aside>
  );
}
