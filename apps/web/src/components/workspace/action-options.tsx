import type {
  DecisionOptionCard,
  GuidanceFreeformAffordance,
  SuggestionOption,
} from "../../lib/types";

interface ActionOptionsProps {
  onSelect?: (option: string) => void;
  onRequestFreeSupplement?: () => void;
  freeformAffordance?: GuidanceFreeformAffordance | null;
  optionCards?: DecisionOptionCard[];
  options: SuggestionOption[];
}

export function ActionOptions({
  onSelect,
  onRequestFreeSupplement,
  freeformAffordance = null,
  optionCards = [],
  options,
}: ActionOptionsProps) {
  const cards = optionCards.length
    ? optionCards
    : options.map((option, index) => ({
        id: `${option.label}-${index}`,
        label: option.label,
        title: option.label,
        content: option.content,
        description: option.rationale,
        type: option.type,
        priority: option.priority,
      }));

  return (
    <div className="space-y-2.5">
      <div className="grid gap-2 sm:grid-cols-3">
        {cards.map((option, index) => (
          <button
            key={option.id}
            className="cursor-pointer rounded-xl border border-stone-200 bg-white px-4 py-3.5 text-left text-sm transition-all duration-150 hover:border-stone-400 hover:shadow-sm active:scale-[0.98]"
            onClick={() => onSelect?.(option.content)}
            type="button"
          >
            <span className="block text-[10px] font-bold uppercase tracking-[0.28em] text-stone-400">
              方案 {String.fromCharCode(65 + index)}
            </span>
            <span className="mt-2 block text-sm font-medium leading-5 text-stone-800">{option.title}</span>
            <span className="mt-1 block text-xs leading-5 text-stone-700">{option.content}</span>
            {option.description ? (
              <span className="mt-2 block text-xs leading-5 text-stone-500">{option.description}</span>
            ) : null}
          </button>
        ))}
      </div>
      {freeformAffordance ? (
        <button
          aria-label={freeformAffordance.label}
          className="flex w-full cursor-pointer items-center justify-between rounded-xl border border-dashed border-stone-300 bg-stone-50 px-4 py-3 text-left text-sm text-stone-700 transition-all duration-150 hover:border-stone-500 hover:bg-white active:scale-[0.99]"
          onClick={() => onRequestFreeSupplement?.()}
          type="button"
        >
          <span className="font-medium text-stone-900">{freeformAffordance.label}</span>
          <span className="text-xs text-stone-500">不预填，我自己补一句</span>
        </button>
      ) : null}
    </div>
  );
}
