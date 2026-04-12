import type { SuggestionOption } from "../../lib/types";

interface ActionOptionsProps {
  onSelect?: (option: string) => void;
  options: SuggestionOption[];
}

export function ActionOptions({ onSelect, options }: ActionOptionsProps) {
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {options.map((option, index) => (
        <button
          key={`${option.label}-${option.content}`}
          className="cursor-pointer rounded-xl border border-stone-200 bg-white px-4 py-3.5 text-left text-sm transition-all duration-150 hover:border-stone-400 hover:shadow-sm active:scale-[0.98]"
          onClick={() => onSelect?.(option.content)}
          type="button"
        >
          <span className="block text-[10px] font-bold uppercase tracking-[0.28em] text-stone-400">
            方案 {String.fromCharCode(65 + index)}
          </span>
          <span className="mt-2 block text-sm font-medium leading-5 text-stone-800">{option.label}</span>
          <span className="mt-1 block text-xs leading-5 text-stone-700">{option.content}</span>
        </button>
      ))}
    </div>
  );
}
