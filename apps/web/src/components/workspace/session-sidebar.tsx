export function SessionSidebar() {
  const sessions = [
    { title: "AI 产品陪跑助手", stage: "理解问题", active: true },
    { title: "独立开发者 PRD 生成器", stage: "定义 MVP", active: false },
    { title: "出海工具导航", stage: "验证需求", active: false },
  ];

  return (
    <aside className="flex h-full flex-col rounded-[28px] border border-stone-200 bg-stone-50 p-5 shadow-sm">
      <div className="space-y-1 border-b border-stone-200 pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">
          Project Board
        </p>
        <h2 className="text-2xl font-semibold text-stone-950">项目面板</h2>
        <p className="text-sm leading-6 text-stone-600">
          把每次讨论放在清晰上下文里，而不是散落在聊天历史里。
        </p>
      </div>

      <button
        className="mt-5 rounded-2xl border border-stone-900 bg-stone-950 px-4 py-3 text-sm font-medium text-white"
        type="button"
      >
        新建项目
      </button>

      <div className="mt-6 space-y-3">
        {sessions.map((session) => (
          <article
            key={session.title}
            className={`rounded-2xl border px-4 py-4 transition ${
              session.active
                ? "border-stone-900 bg-white shadow-sm"
                : "border-stone-200 bg-white/70"
            }`}
          >
            <p className="text-sm font-semibold text-stone-900">{session.title}</p>
            <p className="mt-2 text-xs uppercase tracking-[0.2em] text-stone-500">
              {session.stage}
            </p>
          </article>
        ))}
      </div>

      <div className="mt-auto rounded-2xl border border-dashed border-stone-300 bg-white px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
          Stage
        </p>
        <p className="mt-2 text-lg font-semibold text-stone-900">收敛方案</p>
        <p className="mt-2 text-sm leading-6 text-stone-600">
          目标是让用户在每一轮都做出更接近 PRD 的决策。
        </p>
      </div>
    </aside>
  );
}
