import type { PrdMeta, PrdSection, PrdState, SessionSnapshotResponse, StateSnapshotResponse } from "../lib/types";

const initialPrdSections: Record<string, PrdSection> = {
  target_user: {
    title: "目标用户",
    content: "还需要继续明确谁会最频繁、最迫切地使用这个产品。",
    status: "confirmed",
  },
  problem: {
    title: "核心问题",
    content: "当前只知道用户有想法，但具体痛点、触发场景和替代方案还不够清楚。",
    status: "inferred",
  },
  solution: {
    title: "解决方案",
    content: "系统会通过连续追问、挑战假设和收敛选项，帮助用户把模糊想法变成可执行 PRD。",
    status: "inferred",
  },
  mvp_scope: {
    title: "MVP 范围",
    content: "需要进一步确认首版最小闭环，包括会话、追问、决策沉淀和 PRD 输出。",
    status: "missing",
  },
  constraints: {
    title: "约束条件",
    content: "",
    status: "missing",
  },
  success_metrics: {
    title: "成功指标",
    content: "",
    status: "missing",
  },
  risks_to_validate: {
    title: "待验证 / 风险",
    content: "",
    status: "missing",
  },
  open_questions: {
    title: "待确认问题",
    content: "",
    status: "missing",
  },
};

const initialPrdMeta: PrdMeta = {
  stageLabel: "探索中",
  stageTone: "draft",
  criticSummary: "系统正在持续沉淀当前 PRD 草稿。",
  criticGaps: [],
  draftVersion: null,
  nextQuestion: null,
};

export const prdPanelSectionOrder = [
  "target_user",
  "problem",
  "solution",
  "mvp_scope",
  "constraints",
  "success_metrics",
  "risks_to_validate",
  "open_questions",
] as const;

const legacyDraftSectionKeys = ["out_of_scope"] as const;

export function createInitialPrdSections(): PrdState["sections"] {
  return Object.fromEntries(
    Object.entries(initialPrdSections).map(([key, section]) => [key, { ...section }]),
  );
}

export function createInitialPrdMeta(): PrdState["meta"] {
  return { ...initialPrdMeta };
}

export function createInitialPrdState(): PrdState {
  return {
    meta: createInitialPrdMeta(),
    sectionOrder: [...prdPanelSectionOrder],
    sections: createInitialPrdSections(),
    sectionsChanged: [],
    missingSections: [],
    gapPrompts: [],
    readyForConfirmation: false,
  };
}

export function deriveExtraPrdSections(
  state: Pick<StateSnapshotResponse, "prd_draft">,
): Record<string, PrdSection> {
  const sections = asRecord(asRecord(state.prd_draft).sections);
  const nextSections: Record<string, PrdSection> = {};
  const legacyExtraKeys = new Set<string>([
    "constraints",
    "success_metrics",
    "open_questions",
    "out_of_scope",
  ]);

  for (const [key, value] of Object.entries(sections)) {
    if (!legacyExtraKeys.has(key)) {
      continue;
    }
    const normalized = normalizePrdSection(key, value);
    if (!normalized || !normalized.content.trim()) {
      continue;
    }
    nextSections[key] = normalized;
  }

  return nextSections;
}

export function normalizePrdSection(
  key: string,
  value: unknown,
): PrdSection | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  const record = value as Record<string, unknown>;
  const content = typeof record.content === "string" ? record.content : "";
  const title = typeof record.title === "string" && record.title ? record.title : key;
  const status =
    record.status === "confirmed" ||
    record.status === "inferred" ||
    record.status === "missing"
      ? record.status
      : "missing";

  return { content, title, status };
}

function mergePrdMeta(base: PrdMeta, value: unknown): PrdMeta {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return base;
  }

  const record = value as Record<string, unknown>;
  const stageTone =
    record.stageTone === "draft" ||
    record.stageTone === "ready" ||
    record.stageTone === "final"
      ? record.stageTone
      : base.stageTone;

  return {
    stageLabel: typeof record.stageLabel === "string" ? record.stageLabel : base.stageLabel,
    stageTone,
    criticSummary: typeof record.criticSummary === "string" ? record.criticSummary : base.criticSummary,
    criticGaps: Array.isArray(record.criticGaps) ? asStringArray(record.criticGaps) : base.criticGaps,
    draftVersion: typeof record.draftVersion === "number" ? record.draftVersion : base.draftVersion,
    nextQuestion:
      record.nextQuestion === null
        ? null
        : typeof record.nextQuestion === "string"
          ? record.nextQuestion
          : base.nextQuestion,
  };
}

export function derivePrdMeta(state: StateSnapshotResponse): PrdMeta {
  const workflowStage = asString(state.workflow_stage);
  const finalizationReady = asBoolean(state.finalization_ready) ?? false;
  const prdDraft = asRecord(state.prd_draft);
  const criticResult = asRecord(state.critic_result);
  const draftVersion = asNumber(prdDraft.version);
  const draftStatus = asString(prdDraft.status);
  const overallVerdict = asString(criticResult.overall_verdict);
  const majorGaps = asStringArray(criticResult.major_gaps);
  const questionQueue = asStringArray(criticResult.question_queue);
  const nextQuestion = questionQueue[0] ?? null;

  let stageLabel = "探索中";
  let stageTone: PrdMeta["stageTone"] = "draft";

  if (workflowStage === "completed" || draftStatus === "finalized") {
    stageLabel = "已生成终稿";
    stageTone = "final";
  } else if (workflowStage === "finalize" || finalizationReady || overallVerdict === "pass") {
    stageLabel = "可整理终稿";
    stageTone = "ready";
  } else if (workflowStage === "refine_loop") {
    stageLabel = "草稿中";
    stageTone = "draft";
  }

  let criticSummary = "系统正在持续沉淀当前 PRD 草稿。";
  if (stageLabel === "已生成终稿") {
    criticSummary = "当前会话已经整理出最终版 PRD，后续修改会基于终稿增量更新。";
  } else if (overallVerdict === "pass") {
    criticSummary = "Critic 已通过，可以整理最终版 PRD。";
  } else if (majorGaps.length > 0) {
    criticSummary = `Critic 认为还有 ${majorGaps.length} 个关键缺口待补齐。`;
  } else if (questionQueue.length > 0) {
    criticSummary = `Critic 还在等待 ${questionQueue.length} 个问题的补充。`;
  }

  return {
    stageLabel,
    stageTone,
    criticSummary,
    criticGaps: majorGaps,
    draftVersion,
    nextQuestion,
  };
}

function normalizeSectionMap(sections: Record<string, unknown>): Record<string, PrdSection> {
  const nextSections = createInitialPrdSections();
  for (const key of prdPanelSectionOrder) {
    const normalized = normalizePrdSection(key, sections[key]);
    if (normalized) {
      nextSections[key] = normalized;
    }
  }

  for (const key of legacyDraftSectionKeys) {
    const normalized = normalizePrdSection(key, sections[key]);
    if (normalized && normalized.content.trim()) {
      nextSections[key] = normalized;
    }
  }

  return nextSections;
}

export function normalizePrdSnapshotState(
  snapshot: SessionSnapshotResponse,
): PrdState {
  const snapshotSections = asRecord(snapshot.prd_snapshot.sections);
  const draftSections = asRecord(asRecord(snapshot.state.prd_draft).sections);
  const derivedMeta = derivePrdMeta(snapshot.state);
  const nextSections = normalizeSectionMap({
    ...snapshotSections,
    ...draftSections,
  });

  return {
    meta: mergePrdMeta(derivedMeta, snapshot.prd_snapshot.meta),
    sectionOrder: [...prdPanelSectionOrder],
    sections: nextSections,
    sectionsChanged: asStringArray(snapshot.prd_snapshot.sections_changed),
    missingSections: asStringArray(snapshot.prd_snapshot.missing_sections),
    gapPrompts: asStringArray(snapshot.prd_snapshot.gap_prompts),
    readyForConfirmation: snapshot.prd_snapshot.ready_for_confirmation === true,
  };
}

export function normalizeIncomingPrdPanelUpdate(
  currentPrd: PrdState,
  data: {
    sections: Record<string, unknown>;
    meta?: unknown;
    sections_changed?: string[];
    missing_sections?: string[];
    gap_prompts?: string[];
    ready_for_confirmation?: boolean;
  },
): PrdState {
  const mergedSections = { ...currentPrd.sections };
  for (const key of Object.keys(data.sections ?? {})) {
    const normalized = normalizePrdSection(key, data.sections[key]);
    if (normalized) {
      mergedSections[key] = normalized;
    }
  }

  return {
    meta: mergePrdMeta(currentPrd.meta, data.meta),
    sectionOrder: [...currentPrd.sectionOrder],
    sections: mergedSections,
    sectionsChanged: Array.isArray(data.sections_changed)
      ? data.sections_changed.filter((entry): entry is string => typeof entry === "string")
      : currentPrd.sectionsChanged,
    missingSections: Array.isArray(data.missing_sections)
      ? data.missing_sections.filter((entry): entry is string => typeof entry === "string")
      : currentPrd.missingSections,
    gapPrompts: Array.isArray(data.gap_prompts)
      ? data.gap_prompts.filter((entry): entry is string => typeof entry === "string")
      : currentPrd.gapPrompts,
    readyForConfirmation:
      typeof data.ready_for_confirmation === "boolean"
        ? data.ready_for_confirmation
        : currentPrd.readyForConfirmation,
  };
}

export function shouldPreserveCurrentPrd(
  currentPrd: PrdState,
  nextPrd: PrdState,
): boolean {
  const currentDraftVersion = currentPrd.meta.draftVersion;
  const nextDraftVersion = nextPrd.meta.draftVersion;

  return (
    typeof currentDraftVersion === "number" &&
    typeof nextDraftVersion === "number" &&
    currentDraftVersion > nextDraftVersion
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}
