export function Composer() {
  return (
    <form className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
      <label className="block">
        <span className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
          当前输入
        </span>
        <textarea
          className="mt-3 min-h-32 w-full resize-none rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4 text-sm leading-7 text-stone-800 outline-none transition focus:border-stone-900"
          defaultValue="我想先聚焦那些已经开始做产品，但一直说不清目标用户是谁的独立开发者。"
          placeholder="继续补充你的想法，或者直接选择一个方向。"
        />
      </label>

      <div className="mt-4 flex items-center justify-between gap-4">
        <p className="text-sm text-stone-500">优先用选择推进，必要时再补自由输入。</p>
        <button
          className="rounded-2xl bg-stone-900 px-5 py-3 text-sm font-medium text-white"
          type="button"
        >
          继续推进
        </button>
      </div>
    </form>
  );
}
