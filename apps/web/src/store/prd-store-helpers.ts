import type { PrdState, SessionSnapshotResponse, StateSnapshotResponse } from "../lib/types";

const initialPrdSections: PrdState["sections"] = {
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
};

const initialPrdMeta: PrdState["meta"] = {
  stageLabel: "探索中",
  stageTone: "draft",
  criticSummary: "系统正在持续沉淀当前 PRD 草稿。",
  criticGaps: [],
  draftVersion: null,
  nextQuestion: null,
};

const primaryPrdSectionKeys = ["target_user", "problem", "solution", "mvp_scope"] as const;
const extraPrdSectionKeys = ["constraints", "success_metrics", "out_of_scope", "open_questions"] as const;

export function createInitialPrdSections(): PrdState["sections"] {
  return {
    target_user: { ...initialPrdSections.target_user },
    problem: { ...initialPrdSections.problem },
    solution: { ...initialPrdSections.solution },
    mvp_scope: { ...initialPrdSections.mvp_scope },
  };
}

export function createInitialPrdMeta(): PrdState["meta"] {
  return { ...initialPrdMeta };
}

export function createInitialExtraPrdSections(): PrdState["extraSections"] {
  return {};
}

export function normalizePrdSection(
  key: string,
  value: unknown,
): PrdState["sections"][string] | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  const record = value as Record<string, unknown>;
  const content = typeof record.content === "string" ? record.content : "";
  if (!content.trim()) {
    return null;
  }

  const title = typeof record.title === "string" && record.title ? record.title : key;
  const status =
    record.status === "confirmed" ||
    record.status === "inferred" ||
    record.status === "missing"
      ? record.status
      : "missing";

  return { content, title, status };
}

export function derivePrimaryPrdSections(
  state: Record<string, unknown>,
  snapshotSections: SessionSnapshotResponse["prd_snapshot"]["sections"],
): PrdState["sections"] {
  const prdDraft = asRecord(state.prd_draft);
  const draftSections = asRecord(prdDraft.sections);

  return Object.fromEntries(
    primaryPrdSectionKeys.map((key) => {
      const draftSection = normalizePrdSection(key, draftSections[key]);
      const snapshotSection = normalizePrdSection(key, snapshotSections[key]);
      const fallbackSection = createInitialPrdSections()[key];

      return [key, draftSection ?? snapshotSection ?? fallbackSection];
    }),
  );
}

export function deriveExtraPrdSections(state: StateSnapshotResponse): PrdState["extraSections"] {
  const prdDraft = asRecord(state.prd_draft);
  const rawSections = asRecord(prdDraft.sections);

  return Object.fromEntries(
    extraPrdSectionKeys
      .map((key) => {
        const normalized = normalizePrdSection(key, rawSections[key]);
        return normalized ? ([key, normalized] as const) : null;
      })
      .filter((entry): entry is readonly [string, PrdState["sections"][string]] => entry !== null),
  );
}

export function derivePrdMeta(state: StateSnapshotResponse): PrdState["meta"] {
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
  let stageTone: PrdState["meta"]["stageTone"] = "draft";

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

export function normalizeIncomingPrdSections(
  sections: Record<string, PrdState["sections"][string]>,
): Pick<PrdState, "sections" | "extraSections"> {
  const nextSections: PrdState["sections"] = {};
  const nextExtraSections: PrdState["extraSections"] = {};

  for (const key of primaryPrdSectionKeys) {
    const normalized = normalizePrdSection(key, sections[key]);
    if (normalized) {
      nextSections[key] = normalized;
    }
  }

  for (const key of extraPrdSectionKeys) {
    const normalized = normalizePrdSection(key, sections[key]);
    if (normalized) {
      nextExtraSections[key] = normalized;
    }
  }

  return {
    sections: nextSections,
    extraSections: nextExtraSections,
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
