"use client";

import type { Ref } from "react";

import { useWorkspaceStore } from "../../store/workspace-store";

interface ModelSelectorProps {
  onSelectModel?: () => void;
  selectRef?: Ref<HTMLSelectElement>;
}

export function ModelSelector({ onSelectModel, selectRef }: ModelSelectorProps) {
  const availableModelConfigs = useWorkspaceStore((state) => state.availableModelConfigs);
  const selectedModelConfigId = useWorkspaceStore((state) => state.selectedModelConfigId);
  const selectModelConfig = useWorkspaceStore((state) => state.selectModelConfig);

  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">
        选择模型
      </span>
      <select
        aria-label="选择模型"
        className="min-w-[220px] rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-800 outline-none transition-all duration-150 hover:border-stone-300 focus:border-stone-900 focus:bg-white focus:ring-2 focus:ring-stone-900/8 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={availableModelConfigs.length === 0}
        onChange={(event) => {
          onSelectModel?.();
          selectModelConfig(event.target.value);
        }}
        ref={selectRef}
        value={selectedModelConfigId ?? ""}
      >
        {availableModelConfigs.length === 0 ? (
          <option value="">暂无可用模型</option>
        ) : null}
        {availableModelConfigs.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name} · {item.model}
          </option>
        ))}
      </select>
    </label>
  );
}
