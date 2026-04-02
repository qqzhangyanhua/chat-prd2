const options = [
  "继续追问早期创业者",
  "收窄到独立开发者",
  "直接定义第一个 MVP 人群",
];


export function ActionOptions() {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {options.map((option, index) => (
        <button
          key={option}
          className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4 text-left text-sm font-medium text-stone-800 transition hover:border-stone-900 hover:bg-white"
          type="button"
        >
          <span className="block text-xs uppercase tracking-[0.24em] text-stone-500">
            选项 {String.fromCharCode(65 + index)}
          </span>
          <span className="mt-3 block leading-6">{option}</span>
        </button>
      ))}
    </div>
  );
}
