import { useStore } from "zustand";
import { createStore } from "zustand/vanilla";

import type {
  AgentTurnDecision,
  DecisionDiagnosticBucket,
  DecisionDiagnosticItem,
  DecisionDiagnosticSummary,
  DecisionOptionCard,
  DecisionReadyData,
  DecisionGuidance,
  DiagnosticLedgerGroup,
  GuidanceFreeformAffordance,
  GuidanceMode,
  GuidanceModeSwitch,
  GuidanceResponseMode,
  GuidanceStep,
  DecisionStrategy,
  AssistantReplyGroup,
  AssistantReplyVersion,
  ConversationMessage,
  DraftUpdatedData,
  EnabledModelConfigItem,
  FirstDraftCompleteness,
  FirstDraftEntry,
  FirstDraftEvidenceItem,
  FirstDraftSection,
  FirstDraftState,
  NextAction,
  PrdState,
  PrdReviewResponse,
  ReplayTimelineItem,
  RecommendedScene,
  SessionSnapshotResponse,
  StateSnapshotResponse,
  SuggestionOption,
  WorkflowStage,
  WorkspaceEvent,
  WorkspaceMessage,
} from "../lib/types";
import {
  createInitialPrdState,
  normalizeIncomingPrdPanelUpdate,
  normalizePrdSnapshotState,
  shouldPreserveCurrentPrd,
} from "./prd-store-helpers";

type StreamPhase = "idle" | "waiting" | "streaming";
type RequestMode = "new" | "regenerate";

interface WorkspaceReplyVersion {
  assistantMessageId: string | null;
  content: string;
  createdAt?: string;
  id: string;
  isLatest: boolean;
  isRegeneration: boolean;
  versionNo: number;
}

interface WorkspaceReplyGroup {
  id: string;
  latestVersionId: string | null;
  sessionId: string;
  userMessageId: string;
  versions: WorkspaceReplyVersion[];
}

interface WorkspaceState {
  activeAssistantVersionId: string | null;
  activeReplyGroupId: string | null;
  availableModelConfigs: EnabledModelConfigItem[];
  collaborationModeLabel: string | null;
  workflowStage: WorkflowStage | null;
  isFinalizeReady: boolean;
  isCompleted: boolean;
  currentAction: NextAction | null;
  currentModelScene: RecommendedScene | null;
  errorMessage: string | null;
  diagnosticLedger: DecisionDiagnosticItem[];
  diagnosticLedgerSummary: DecisionDiagnosticSummary | null;
  inputValue: string;
  isFinalizingSession: boolean;
  isStreaming: boolean;
  lastInterrupted: boolean;
  lastSubmittedInput: string | null;
  messages: WorkspaceMessage[];
  latestDiagnostics: DecisionDiagnosticItem[];
  latestDiagnosticSummary: DecisionDiagnosticSummary | null;
  pendingUserInput: string | null;
  pendingRequestMode: RequestMode | null;
  prd: PrdState;
  prdReview: PrdReviewResponse | null;
  replayTimeline: ReplayTimelineItem[];
  firstDraft: FirstDraftState;
  decisionGuidance: DecisionGuidance | null;
  regenerateRequestId: number;
  replyGroups: Record<string, WorkspaceReplyGroup>;
  selectedModelConfigId: string | null;
  selectedHistoryGroupId: string | null;
  selectedHistoryVersionId: string | null;
  streamPhase: StreamPhase;
  applyEvent: (event: WorkspaceEvent) => void;
  cancelPendingRequest: () => void;
  failRequest: (message: string) => void;
  hydrateSession: (snapshot: SessionSnapshotResponse) => void;
  refreshSessionSnapshot: (snapshot: SessionSnapshotResponse) => void;
  markInterrupted: () => void;
  resetError: () => void;
  selectModelConfig: (modelConfigId: string) => void;
  setAvailableModelConfigs: (items: EnabledModelConfigItem[]) => void;
  setSessionFinalizing: (value: boolean) => void;
  isLeftNavCollapsed: boolean;
  setInputValue: (value: string) => void;
  setLeftNavCollapsed: (collapsed: boolean | ((prev: boolean) => boolean)) => void;
  setStreaming: (value: boolean) => void;
  startRegenerate: () => boolean;
  startRequest: (content: string, mode?: RequestMode) => void;
}

function normalizeWorkflowStage(value: unknown): WorkflowStage | null {
  return value === "idea_parser" ||
      value === "refine_loop" ||
      value === "finalize" ||
      value === "completed"
    ? value
    : null;
}

function deriveWorkflowFlags(state: StateSnapshotResponse): Pick<
  WorkspaceState,
  "workflowStage" | "isFinalizeReady" | "isCompleted"
> {
  const workflowStage = normalizeWorkflowStage(state.workflow_stage);
  const isFinalizeReady = state.finalization_ready === true;
  const isCompleted = state.is_completed === true || workflowStage === "completed";

  return {
    workflowStage,
    isFinalizeReady,
    isCompleted,
  };
}

function isSnapshotOlderByDraftVersion(
  current: Pick<WorkspaceState, "prd">,
  nextState: StateSnapshotResponse,
  nextSnapshot?: SessionSnapshotResponse["prd_snapshot"],
): boolean {
  const currentVersion = current.prd.meta.draftVersion;
  const nextVersionFromMeta =
    nextSnapshot?.meta && typeof nextSnapshot.meta === "object" && typeof nextSnapshot.meta.draftVersion === "number"
      ? nextSnapshot.meta.draftVersion
      : null;
  const prdDraft = nextState.prd_draft;
  const nextVersion = nextVersionFromMeta ?? (
    prdDraft && typeof prdDraft === "object" && typeof prdDraft.version === "number"
      ? prdDraft.version
      : null
  );

  return (
    typeof currentVersion === "number" &&
    typeof nextVersion === "number" &&
    currentVersion > nextVersion
  );
}

const STRATEGY_LABEL_MAP: Record<DecisionStrategy, string> = {
  greet: "欢迎引导",
  clarify: "澄清中",
  choose: "取舍中",
  converge: "收敛中",
  confirm: "确认中",
};
const DECISION_STRATEGY_SET = new Set<DecisionStrategy>([
  "greet",
  "clarify",
  "choose",
  "converge",
  "confirm",
]);
const GUIDANCE_MODE_SET = new Set<GuidanceMode>(["explore", "narrow", "compare", "confirm"]);
const GUIDANCE_STEP_SET = new Set<GuidanceStep>(["answer", "choose", "compare", "confirm", "freeform"]);
const RESPONSE_MODE_SET = new Set<GuidanceResponseMode>(["options_first", "direct_answer", "confirm_reply"]);

function normalizeBestQuestions(items?: unknown[]): string[] {
  if (!items?.length) {
    return [];
  }

  const strings = items.filter((item): item is string => typeof item === "string");
  if (!strings.length) {
    return [];
  }

  const seen = new Set<string>();
  const normalized: string[] = [];

  for (const raw of strings) {
    const next = raw?.trim();
    if (!next || seen.has(next)) {
      continue;
    }
    seen.add(next);
    normalized.push(next);
    if (normalized.length >= 4) {
      break;
    }
  }

  return normalized;
}

function normalizeSuggestionOptions(items?: unknown[]): SuggestionOption[] {
  if (!items?.length) {
    return [];
  }

  const normalized: SuggestionOption[] = [];

  for (const item of items) {
    if (!item || typeof item !== "object") {
      continue;
    }

    const candidate = item as Record<string, unknown>;
    const label = typeof candidate.label === "string" ? candidate.label.trim() : "";
    const content = typeof candidate.content === "string" ? candidate.content.trim() : "";
    const rationale = typeof candidate.rationale === "string" ? candidate.rationale.trim() : "";
    const type = typeof candidate.type === "string" ? candidate.type.trim() : "direction";
    const priority = typeof candidate.priority === "number" && candidate.priority > 0
      ? candidate.priority
      : normalized.length + 1;

    if (!label || !content || !rationale) {
      continue;
    }

    if (normalized.some((option) => option.label === label && option.content === content)) {
      continue;
    }

    normalized.push({
      label,
      content,
      rationale,
      priority,
      type,
    });

    if (normalized.length >= 4) {
      break;
    }
  }

  return normalized.sort((a, b) => a.priority - b.priority);
}

function normalizeOptionCards(items?: unknown[]): DecisionOptionCard[] {
  if (!items?.length) {
    return [];
  }

  const normalized: DecisionOptionCard[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const candidate = item as Record<string, unknown>;
    const id = typeof candidate.id === "string" ? candidate.id.trim() : "";
    const label = typeof candidate.label === "string" ? candidate.label.trim() : "";
    const title = typeof candidate.title === "string" ? candidate.title.trim() : label;
    const content = typeof candidate.content === "string" ? candidate.content.trim() : "";
    const description = typeof candidate.description === "string" ? candidate.description.trim() : "";
    const type = typeof candidate.type === "string" ? candidate.type.trim() : "direction";
    const priority = typeof candidate.priority === "number" && candidate.priority > 0
      ? candidate.priority
      : normalized.length + 1;
    if (!id || !label || !title || !content) {
      continue;
    }
    if (normalized.some((card) => card.id === id)) {
      continue;
    }
    normalized.push({ id, label, title, content, description, type, priority });
    if (normalized.length >= 4) {
      break;
    }
  }
  return normalized.sort((a, b) => a.priority - b.priority);
}

function normalizeFreeformAffordance(value?: unknown): GuidanceFreeformAffordance | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  const label = typeof candidate.label === "string" ? candidate.label.trim() : "";
  const val = typeof candidate.value === "string" ? candidate.value.trim() : "";
  const kind = typeof candidate.kind === "string" ? candidate.kind.trim() : "";
  if (!label || !val || !kind) {
    return null;
  }
  return { label, value: val, kind };
}

function normalizeModeSwitches(items?: unknown[]): GuidanceModeSwitch[] {
  if (!items?.length) {
    return [];
  }
  const normalized: GuidanceModeSwitch[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const candidate = item as Record<string, unknown>;
    const mode = typeof candidate.mode === "string" ? candidate.mode.trim() : "";
    const label = typeof candidate.label === "string" ? candidate.label.trim() : "";
    if (!mode || !label) {
      continue;
    }
    if (normalized.some((current) => current.mode === mode && current.label === label)) {
      continue;
    }
    normalized.push({ mode, label });
  }
  return normalized;
}

function normalizeGuidanceMode(value?: unknown): GuidanceMode | null {
  return typeof value === "string" && GUIDANCE_MODE_SET.has(value as GuidanceMode)
    ? value as GuidanceMode
    : null;
}

function normalizeGuidanceStep(value?: unknown): GuidanceStep | null {
  return typeof value === "string" && GUIDANCE_STEP_SET.has(value as GuidanceStep)
    ? value as GuidanceStep
    : null;
}

function normalizeResponseMode(value?: unknown): GuidanceResponseMode | null {
  return typeof value === "string" && RESPONSE_MODE_SET.has(value as GuidanceResponseMode)
    ? value as GuidanceResponseMode
    : null;
}

function normalizeDiagnosticSummary(value?: unknown): DecisionDiagnosticSummary | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  const openCount = typeof candidate.open_count === "number"
    ? candidate.open_count
    : typeof candidate.openCount === "number"
      ? candidate.openCount
      : null;
  const unknownCount = typeof candidate.unknown_count === "number"
    ? candidate.unknown_count
    : typeof candidate.unknownCount === "number"
      ? candidate.unknownCount
      : null;
  const riskCount = typeof candidate.risk_count === "number"
    ? candidate.risk_count
    : typeof candidate.riskCount === "number"
      ? candidate.riskCount
      : null;
  const toValidateCount = typeof candidate.to_validate_count === "number"
    ? candidate.to_validate_count
    : typeof candidate.toValidateCount === "number"
      ? candidate.toValidateCount
      : null;
  if (
    openCount === null ||
    unknownCount === null ||
    riskCount === null ||
    toValidateCount === null
  ) {
    return null;
  }
  return {
    openCount,
    unknownCount,
    riskCount,
    toValidateCount,
  };
}

function normalizeDiagnostics(items?: unknown[]): DecisionDiagnosticItem[] {
  if (!items?.length) {
    return [];
  }
  const normalized: DecisionDiagnosticItem[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const candidate = item as Record<string, unknown>;
    const id = typeof candidate.id === "string" ? candidate.id.trim() : "";
    const type = candidate.type;
    const bucket = candidate.bucket;
    const status = candidate.status;
    const title = typeof candidate.title === "string" ? candidate.title.trim() : "";
    const detail = typeof candidate.detail === "string" ? candidate.detail.trim() : "";
    const impactScopeRaw = candidate.impact_scope ?? candidate.impactScope;
    const nextStepRaw = candidate.suggested_next_step ?? candidate.suggestedNextStep;
    const confidence = candidate.confidence;
    if (!id || !title || !detail) {
      continue;
    }
    if (type !== "contradiction" && type !== "gap" && type !== "assumption") {
      continue;
    }
    if (bucket !== "unknown" && bucket !== "risk" && bucket !== "to_validate") {
      continue;
    }
    if (status !== "open" && status !== "resolved" && status !== "superseded") {
      continue;
    }
    if (!Array.isArray(impactScopeRaw)) {
      continue;
    }
    const impactScope = impactScopeRaw
      .filter((part): part is string => typeof part === "string")
      .map((part) => part.trim())
      .filter(Boolean);
    if (!impactScope.length || !nextStepRaw || typeof nextStepRaw !== "object") {
      continue;
    }
    const nextStep = nextStepRaw as Record<string, unknown>;
    const actionKind = typeof nextStep.action_kind === "string"
      ? nextStep.action_kind.trim()
      : typeof nextStep.actionKind === "string"
        ? nextStep.actionKind.trim()
        : "";
    const label = typeof nextStep.label === "string" ? nextStep.label.trim() : "";
    const prompt = typeof nextStep.prompt === "string" ? nextStep.prompt.trim() : "";
    if (!actionKind || !label || !prompt) {
      continue;
    }
    if (normalized.some((current) => current.id === id)) {
      continue;
    }
    normalized.push({
      id,
      type,
      bucket,
      status,
      title,
      detail,
      impactScope,
      suggestedNextStep: {
        action_kind: actionKind,
        label,
        prompt,
      },
      confidence: confidence === "high" || confidence === "medium" || confidence === "low"
        ? confidence
        : "medium",
    });
  }
  return normalized;
}

function normalizeAssertionState(value: unknown): FirstDraftEntry["assertionState"] | null {
  return value === "confirmed" || value === "inferred" || value === "to_validate"
    ? value
    : null;
}

function normalizeFirstDraftCompleteness(value: unknown): FirstDraftCompleteness {
  return value === "complete" || value === "partial" || value === "missing"
    ? value
    : "missing";
}

function normalizeFirstDraftEntry(item: unknown): FirstDraftEntry | null {
  if (!item || typeof item !== "object") {
    return null;
  }
  const candidate = item as Record<string, unknown>;
  const id = typeof candidate.id === "string" ? candidate.id.trim() : "";
  const text = typeof candidate.text === "string" ? candidate.text.trim() : "";
  const assertionState = normalizeAssertionState(candidate.assertion_state ?? candidate.assertionState);
  const evidenceRefIds = Array.isArray(candidate.evidence_ref_ids ?? candidate.evidenceRefIds)
    ? (candidate.evidence_ref_ids ?? candidate.evidenceRefIds as unknown[])
        .filter((entry): entry is string => typeof entry === "string")
        .map((entry) => entry.trim())
        .filter(Boolean)
    : [];
  if (!id || !text || !assertionState) {
    return null;
  }
  return { id, text, assertionState, evidenceRefIds };
}

function normalizeFirstDraftSection(item: unknown): FirstDraftSection | null {
  if (!item || typeof item !== "object") {
    return null;
  }
  const candidate = item as Record<string, unknown>;
  const title = typeof candidate.title === "string" ? candidate.title.trim() : "";
  const entries = Array.isArray(candidate.entries)
    ? candidate.entries
        .map((entry) => normalizeFirstDraftEntry(entry))
        .filter((entry): entry is FirstDraftEntry => entry !== null)
    : [];
  if (!title) {
    return null;
  }
  return {
    title,
    completeness: normalizeFirstDraftCompleteness(candidate.completeness),
    entries,
    summary: typeof candidate.summary === "string" ? candidate.summary : null,
  };
}

function normalizeFirstDraftEvidence(item: unknown): FirstDraftEvidenceItem | null {
  if (!item || typeof item !== "object") {
    return null;
  }
  const candidate = item as Record<string, unknown>;
  const id = typeof candidate.id === "string" ? candidate.id.trim() : "";
  const kind = candidate.kind;
  const excerpt = typeof candidate.excerpt === "string" ? candidate.excerpt.trim() : "";
  const sectionKeysRaw = candidate.section_keys ?? candidate.sectionKeys;
  if (
    kind !== "user_message" &&
    kind !== "assistant_decision" &&
    kind !== "system_inference" &&
    kind !== "diagnostic"
  ) {
    return null;
  }
  if (!id || !excerpt || !Array.isArray(sectionKeysRaw)) {
    return null;
  }
  return {
    id,
    kind,
    excerpt,
    sectionKeys: sectionKeysRaw
      .filter((entry): entry is string => typeof entry === "string")
      .map((entry) => entry.trim())
      .filter(Boolean),
    messageId: typeof candidate.message_id === "string"
      ? candidate.message_id
      : typeof candidate.messageId === "string"
        ? candidate.messageId
        : null,
    turnDecisionId: typeof candidate.turn_decision_id === "string"
      ? candidate.turn_decision_id
      : typeof candidate.turnDecisionId === "string"
        ? candidate.turnDecisionId
        : null,
    createdAt: typeof candidate.created_at === "string"
      ? candidate.created_at
      : typeof candidate.createdAt === "string"
        ? candidate.createdAt
        : null,
  };
}

function createInitialFirstDraftState(): FirstDraftState {
  return {
    version: null,
    status: null,
    sections: {},
    evidenceRegistry: {},
    latestUpdates: {
      version: null,
      sectionKeys: [],
      entryIds: [],
      evidenceIds: [],
    },
  };
}

function normalizeFirstDraftState(
  prdDraft: StateSnapshotResponse["prd_draft"],
  evidence: StateSnapshotResponse["evidence"],
  decision?: AgentTurnDecision | null,
): FirstDraftState {
  if (!prdDraft || typeof prdDraft !== "object") {
    return createInitialFirstDraftState();
  }
  const sectionsRaw = typeof prdDraft.sections === "object" && prdDraft.sections ? prdDraft.sections : {};
  const sections: Record<string, FirstDraftSection> = {};
  Object.entries(sectionsRaw).forEach(([key, value]) => {
    const section = normalizeFirstDraftSection(value);
    if (section) {
      sections[key] = section;
    }
  });
  const evidenceRegistry = Object.fromEntries(
    (Array.isArray(evidence) ? evidence : [])
      .map((item) => normalizeFirstDraftEvidence(item))
      .filter((item): item is FirstDraftEvidenceItem => item !== null)
      .map((item) => [item.id, item]),
  );
  const nextStepMeta = decision?.decision_sections?.find((section) => section.key === "next_step")?.meta;
  const draftUpdates = nextStepMeta?.draft_updates && typeof nextStepMeta.draft_updates === "object"
    ? nextStepMeta.draft_updates as Record<string, unknown>
    : typeof prdDraft.summary === "object" && prdDraft.summary
      ? prdDraft.summary as Record<string, unknown>
      : {};

  return {
    version: typeof prdDraft.version === "number" ? prdDraft.version : null,
    status: typeof prdDraft.status === "string" ? prdDraft.status : null,
    sections,
    evidenceRegistry,
    latestUpdates: {
      version: typeof draftUpdates.version === "number"
        ? draftUpdates.version
        : typeof prdDraft.version === "number"
          ? prdDraft.version
          : null,
      sectionKeys: Array.isArray(draftUpdates.section_keys ?? draftUpdates.sectionKeys)
        ? (draftUpdates.section_keys ?? draftUpdates.sectionKeys as unknown[])
            .filter((entry): entry is string => typeof entry === "string")
        : [],
      entryIds: Array.isArray(draftUpdates.entry_ids ?? draftUpdates.entryIds)
        ? (draftUpdates.entry_ids ?? draftUpdates.entryIds as unknown[])
            .filter((entry): entry is string => typeof entry === "string")
        : [],
      evidenceIds: Array.isArray(draftUpdates.evidence_ids ?? draftUpdates.evidenceIds)
        ? (draftUpdates.evidence_ids ?? draftUpdates.evidenceIds as unknown[])
            .filter((entry): entry is string => typeof entry === "string")
        : Array.isArray(nextStepMeta?.evidence_ref_ids)
          ? nextStepMeta.evidence_ref_ids.filter((entry): entry is string => typeof entry === "string")
          : [],
    },
  };
}

function isOlderFirstDraftVersion(current: FirstDraftState, nextDraft: FirstDraftState): boolean {
  return (
    typeof current.version === "number" &&
    typeof nextDraft.version === "number" &&
    current.version > nextDraft.version
  );
}

function mergeDiagnosticLedger(
  current: DecisionDiagnosticItem[],
  incoming: DecisionDiagnosticItem[],
): DecisionDiagnosticItem[] {
  const ledger = new Map<string, DecisionDiagnosticItem>();
  current.forEach((item) => ledger.set(item.id, item));
  incoming.forEach((item) => {
    if (item.status === "open") {
      ledger.set(item.id, item);
      return;
    }
    ledger.delete(item.id);
  });
  return Array.from(ledger.values());
}

function summarizeDiagnosticLedger(items: DecisionDiagnosticItem[]): DecisionDiagnosticSummary {
  return {
    openCount: items.length,
    unknownCount: items.filter((item) => item.bucket === "unknown").length,
    riskCount: items.filter((item) => item.bucket === "risk").length,
    toValidateCount: items.filter((item) => item.bucket === "to_validate").length,
  };
}

export function buildDiagnosticLedgerGroups(items: DecisionDiagnosticItem[]): DiagnosticLedgerGroup[] {
  const buckets: Array<{ bucket: DecisionDiagnosticBucket; label: string }> = [
    { bucket: "unknown", label: "未知项" },
    { bucket: "risk", label: "风险" },
    { bucket: "to_validate", label: "待验证" },
  ];
  return buckets.map(({ bucket, label }) => ({
    bucket,
    label,
    items: items.filter((item) => item.status === "open" && item.bucket === bucket),
  }));
}

function pickLatestDecision(decisions?: AgentTurnDecision[]): AgentTurnDecision | null {
  if (!decisions?.length) {
    return null;
  }

  const lastDecision = decisions[decisions.length - 1];
  const lastTimestamp = lastDecision.created_at ? Date.parse(lastDecision.created_at) : NaN;
  if (!Number.isFinite(lastTimestamp)) {
    return lastDecision;
  }

  const parsedDecisions = decisions
    .map((decision) => ({
      decision,
      timestamp: decision.created_at ? Date.parse(decision.created_at) : NaN,
    }))
    .filter(({ timestamp }) => Number.isFinite(timestamp))
    .sort((a, b) => b.timestamp - a.timestamp);

  return parsedDecisions[0]?.decision ?? lastDecision;
}

function deriveLatestDiagnostics(decision: AgentTurnDecision | null): {
  latestDiagnostics: DecisionDiagnosticItem[];
  latestDiagnosticSummary: DecisionDiagnosticSummary | null;
} {
  if (!decision) {
    return {
      latestDiagnostics: [],
      latestDiagnosticSummary: null,
    };
  }
  const nextStepMeta = decision.decision_sections?.find((section) => section.key === "next_step")?.meta;
  return {
    latestDiagnostics: normalizeDiagnostics(nextStepMeta?.diagnostics ?? decision.state_patch_json?.diagnostics),
    latestDiagnosticSummary: normalizeDiagnosticSummary(
      nextStepMeta?.diagnostic_summary ?? decision.state_patch_json?.diagnostic_summary,
    ),
  };
}

function deriveDecisionGuidance(decision: AgentTurnDecision): DecisionGuidance | null {
  const judgementMeta = decision.decision_sections?.find((section) => section.key === "judgement")?.meta;
  const nextStepMeta = decision.decision_sections?.find((section) => section.key === "next_step")?.meta;
  const explicitStrategy =
    judgementMeta?.conversation_strategy ?? deductionStrategyFromState(decision.state_patch_json);

  const conversationStrategy = mapStrategy(explicitStrategy);
  const strategyLabelSource =
    judgementMeta?.strategy_label;
  const mappedLabel = STRATEGY_LABEL_MAP[conversationStrategy];
  const strategyLabel = strategyLabelSource ?? mappedLabel ?? "继续推进";
  const transitionReason =
    typeof nextStepMeta?.transition_reason === "string"
      ? nextStepMeta.transition_reason
      : typeof judgementMeta?.transition_reason === "string"
        ? judgementMeta.transition_reason
        : typeof decision.state_patch_json?.transition_reason === "string"
          ? decision.state_patch_json.transition_reason
          : null;
  const strategyReason =
    judgementMeta?.strategy_reason ?? transitionReason ?? decision.state_patch_json?.strategy_reason ?? null;

  const metaNextQuestions = nextStepMeta?.next_best_questions;
  const fallbackNextQuestions = decision.state_patch_json?.next_best_questions;
  const nextBestQuestions = normalizeBestQuestions(metaNextQuestions ?? fallbackNextQuestions);
  const confirmQuickReplies = normalizeBestQuestions(nextStepMeta?.confirm_quick_replies);
  const suggestionOptions = normalizeSuggestionOptions(nextStepMeta?.suggestion_options);
  const optionCards = normalizeOptionCards(nextStepMeta?.option_cards);
  const freeformAffordance = normalizeFreeformAffordance(
    nextStepMeta?.freeform_affordance ?? decision.state_patch_json?.freeform_affordance,
  );
  const availableModeSwitches = normalizeModeSwitches(
    nextStepMeta?.available_mode_switches ?? decision.state_patch_json?.available_mode_switches,
  );
  const guidanceMode = normalizeGuidanceMode(
    nextStepMeta?.guidance_mode ?? judgementMeta?.guidance_mode ?? decision.state_patch_json?.guidance_mode,
  );
  const guidanceStep = normalizeGuidanceStep(
    nextStepMeta?.guidance_step ?? judgementMeta?.guidance_step ?? decision.state_patch_json?.guidance_step,
  );
  const focusDimension = typeof (
    nextStepMeta?.focus_dimension ?? judgementMeta?.focus_dimension ?? decision.state_patch_json?.focus_dimension
  ) === "string"
    ? String(nextStepMeta?.focus_dimension ?? judgementMeta?.focus_dimension ?? decision.state_patch_json?.focus_dimension)
    : null;
  const responseMode = normalizeResponseMode(
    nextStepMeta?.response_mode ?? decision.state_patch_json?.response_mode,
  );

  return buildDecisionGuidance({
    conversationStrategy,
    strategyLabel,
    strategyReason,
    guidanceMode,
    guidanceStep,
    focusDimension,
    transitionReason,
    responseMode,
    nextBestQuestions,
    confirmQuickReplies,
    suggestionOptions,
    optionCards,
    freeformAffordance,
    availableModeSwitches,
  });
}

function deductionStrategyFromState(statePatch?: AgentTurnDecision["state_patch_json"]): string | undefined {
  return statePatch?.conversation_strategy;
}

function mapStrategy(value?: string): DecisionStrategy {
  if (value && DECISION_STRATEGY_SET.has(value as DecisionStrategy)) {
    return value as DecisionStrategy;
  }
  return "clarify";
}

function deriveGuidanceFromDecisionReady(data: DecisionReadyData): DecisionGuidance | null {
  const conversationStrategy = mapStrategy(data.conversation_strategy);
  const strategyLabel = STRATEGY_LABEL_MAP[conversationStrategy] ?? "继续推进";
  const nextBestQuestions = normalizeBestQuestions(data.next_best_questions);
  const suggestionOptions = normalizeSuggestionOptions(data.suggestions);
  const optionCards = normalizeOptionCards(data.option_cards);
  const freeformAffordance = normalizeFreeformAffordance(data.freeform_affordance);
  const availableModeSwitches = normalizeModeSwitches(data.available_mode_switches);
  const transitionReason = typeof data.transition_reason === "string" ? data.transition_reason : null;

  return buildDecisionGuidance({
    conversationStrategy,
    strategyLabel,
    strategyReason: transitionReason,
    guidanceMode: normalizeGuidanceMode(data.guidance_mode),
    guidanceStep: normalizeGuidanceStep(data.guidance_step),
    focusDimension: typeof data.focus_dimension === "string" ? data.focus_dimension : null,
    transitionReason,
    responseMode: normalizeResponseMode(data.response_mode),
    nextBestQuestions,
    confirmQuickReplies: [],
    suggestionOptions,
    optionCards,
    freeformAffordance,
    availableModeSwitches,
  });
}

function buildDecisionGuidance(input: {
  conversationStrategy: DecisionStrategy;
  strategyLabel: string;
  strategyReason: string | null;
  guidanceMode: GuidanceMode | null;
  guidanceStep: GuidanceStep | null;
  focusDimension: string | null;
  transitionReason: string | null;
  responseMode: GuidanceResponseMode | null;
  nextBestQuestions: string[];
  confirmQuickReplies: string[];
  suggestionOptions: SuggestionOption[];
  optionCards: DecisionOptionCard[];
  freeformAffordance: GuidanceFreeformAffordance | null;
  availableModeSwitches: GuidanceModeSwitch[];
}): DecisionGuidance | null {
  const {
    conversationStrategy,
    strategyLabel,
    strategyReason,
    guidanceMode,
    guidanceStep,
    focusDimension,
    transitionReason,
    responseMode,
    nextBestQuestions,
    confirmQuickReplies,
    suggestionOptions,
    optionCards,
    freeformAffordance,
    availableModeSwitches,
  } = input;

  if (!nextBestQuestions.length && !suggestionOptions.length && !optionCards.length && !freeformAffordance) {
    return null;
  }

  return {
    conversationStrategy,
    strategyLabel,
    strategyReason,
    nextBestQuestions,
    confirmQuickReplies,
    ...(guidanceMode ? { guidanceMode } : {}),
    ...(guidanceStep ? { guidanceStep } : {}),
    ...(focusDimension ? { focusDimension } : {}),
    ...(transitionReason ? { transitionReason } : {}),
    ...(responseMode ? { responseMode } : {}),
    ...(optionCards.length ? { optionCards } : {}),
    ...(freeformAffordance ? { freeformAffordance } : {}),
    ...(availableModeSwitches.length ? { availableModeSwitches } : {}),
    ...(suggestionOptions.length ? { suggestionOptions } : {}),
  };
}

function deriveGuidanceFromSnapshot(snapshot: SessionSnapshotResponse): DecisionGuidance | null {
  const latest = pickLatestDecision(snapshot.turn_decisions ?? []);
  if (!latest) {
    return null;
  }

  return deriveDecisionGuidance(latest);
}

function normalizePrdReview(review: SessionSnapshotResponse["prd_review"]): PrdReviewResponse | null {
  if (!review || typeof review !== "object") {
    return null;
  }
  const checks = review.checks && typeof review.checks === "object" ? review.checks : {};
  return {
    verdict: typeof review.verdict === "string" ? review.verdict : "needs_input",
    status: typeof review.status === "string" ? review.status : "drafting",
    summary: typeof review.summary === "string" ? review.summary : "",
    checks: Object.fromEntries(
      Object.entries(checks).map(([key, value]) => {
        const candidate = value && typeof value === "object" ? value as Record<string, unknown> : {};
        return [key, {
          verdict: typeof candidate.verdict === "string" ? candidate.verdict : "needs_input",
          summary: typeof candidate.summary === "string" ? candidate.summary : "",
          evidence: Array.isArray(candidate.evidence)
            ? candidate.evidence.filter((entry): entry is string => typeof entry === "string")
            : [],
        }];
      }),
    ),
    gaps: Array.isArray(review.gaps) ? review.gaps.filter((entry): entry is string => typeof entry === "string") : [],
    missing_sections: Array.isArray(review.missing_sections)
      ? review.missing_sections.filter((entry): entry is string => typeof entry === "string")
      : [],
    ready_for_confirmation: review.ready_for_confirmation === true,
  };
}

function normalizeReplayTimeline(items?: SessionSnapshotResponse["replay_timeline"]): ReplayTimelineItem[] {
  if (!Array.isArray(items)) {
    return [];
  }
  const allowedTypes = new Set<ReplayTimelineItem["type"]>([
    "guidance",
    "diagnostics",
    "prd_delta",
    "finalize",
    "export",
  ]);
  return items
    .filter((item): item is ReplayTimelineItem => Boolean(
      item &&
      typeof item === "object" &&
      typeof item.id === "string" &&
      typeof item.title === "string" &&
      typeof item.summary === "string" &&
      allowedTypes.has(item.type),
    ))
    .map((item) => ({
      ...item,
      sections_changed: Array.isArray(item.sections_changed)
        ? item.sections_changed.filter((entry): entry is string => typeof entry === "string")
        : [],
      metadata: item.metadata && typeof item.metadata === "object" ? item.metadata : {},
    }));
}

function normalizeMessages(messages: ConversationMessage[]): WorkspaceMessage[] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      replyGroupId: message.reply_group_id,
      versionNo: message.version_no,
      isLatest: message.is_latest,
    }));
}

function normalizeReplyGroups(groups: AssistantReplyGroup[]): Record<string, WorkspaceReplyGroup> {
  return Object.fromEntries(
    groups.map((group) => [
      group.id,
      {
        id: group.id,
        sessionId: group.session_id,
        userMessageId: group.user_message_id,
        latestVersionId: group.latest_version_id,
        versions: group.versions
          .slice()
          .sort((a, b) => a.version_no - b.version_no)
          .map((version: AssistantReplyVersion) => ({
            id: version.id,
            versionNo: version.version_no,
            content: version.content,
            createdAt: version.created_at,
            assistantMessageId: null,
            isRegeneration: version.version_no > 1,
            isLatest: version.is_latest ?? version.id === group.latest_version_id,
          })),
      },
    ]),
  );
}

function buildHydratedSessionState(
  state: Omit<WorkspaceState, "applyEvent" | "cancelPendingRequest" | "failRequest" | "hydrateSession" | "refreshSessionSnapshot" | "markInterrupted" | "resetError" | "selectModelConfig" | "setAvailableModelConfigs" | "setInputValue" | "setLeftNavCollapsed" | "setStreaming" | "startRegenerate" | "startRequest"> & {
    replyGroups: Record<string, WorkspaceReplyGroup>;
    messages: WorkspaceMessage[];
  },
  snapshot: SessionSnapshotResponse,
  options?: {
    preserveCurrentAction?: boolean;
    preserveInputValue?: boolean;
    preserveLastSubmittedInput?: boolean;
    preserveFresherPrd?: boolean;
  },
) {
  const preserveCurrentAction = options?.preserveCurrentAction ?? false;
  const preserveInputValue = options?.preserveInputValue ?? false;
  const preserveLastSubmittedInput = options?.preserveLastSubmittedInput ?? false;
  const preserveFresherPrd = options?.preserveFresherPrd ?? false;
  const fallbackLastSubmittedInput = [...snapshot.messages]
    .reverse()
    .find((message) => message.role === "user")
    ?.content ?? null;
  const nextPrd = normalizePrdSnapshotState(snapshot);
  const preserveByPrdVersion = preserveFresherPrd && shouldPreserveCurrentPrd(state.prd, nextPrd);
  const preserveByWorkflowSemantics = preserveFresherPrd && isSnapshotOlderByDraftVersion(state, snapshot.state, snapshot.prd_snapshot);
  const shouldPreserveSnapshotSemantics = preserveByPrdVersion || preserveByWorkflowSemantics;
  const latestDecision = pickLatestDecision(snapshot.turn_decisions ?? []);
  const nextFirstDraft = normalizeFirstDraftState(snapshot.state.prd_draft, snapshot.state.evidence, latestDecision);
  const derivedDiagnostics = deriveLatestDiagnostics(latestDecision);
  const nextDiagnosticLedger = normalizeDiagnostics(snapshot.state.diagnostics);
  const nextDiagnosticLedgerSummary =
    normalizeDiagnosticSummary(snapshot.state.diagnostic_summary) ??
    summarizeDiagnosticLedger(nextDiagnosticLedger);
  const derivedWorkflowFlags = deriveWorkflowFlags(snapshot.state);
  const workflowFlags = shouldPreserveSnapshotSemantics
    ? {
        workflowStage: state.workflowStage,
        isFinalizeReady: state.isFinalizeReady,
        isCompleted: state.isCompleted,
      }
    : {
        ...derivedWorkflowFlags,
        isFinalizeReady:
          snapshot.prd_snapshot.ready_for_confirmation === true ||
          derivedWorkflowFlags.isFinalizeReady,
      };
  const prd = preserveByPrdVersion ? state.prd : nextPrd;
  const preserveFirstDraft = preserveFresherPrd && isOlderFirstDraftVersion(state.firstDraft, nextFirstDraft);

  return {
    ...state,
    activeAssistantVersionId: null,
    activeReplyGroupId: null,
    collaborationModeLabel:
      typeof snapshot.state.collaboration_mode_label === "string"
        ? snapshot.state.collaboration_mode_label
        : null,
    workflowStage: workflowFlags.workflowStage,
    isFinalizeReady: workflowFlags.isFinalizeReady,
    isCompleted: workflowFlags.isCompleted,
    currentAction: preserveCurrentAction ? state.currentAction : null,
    currentModelScene:
      snapshot.state.current_model_scene === "general" ||
      snapshot.state.current_model_scene === "reasoning" ||
      snapshot.state.current_model_scene === "fallback"
        ? snapshot.state.current_model_scene
        : null,
    errorMessage: null,
    diagnosticLedger: shouldPreserveSnapshotSemantics ? state.diagnosticLedger : nextDiagnosticLedger,
    diagnosticLedgerSummary: shouldPreserveSnapshotSemantics
      ? state.diagnosticLedgerSummary
      : nextDiagnosticLedgerSummary,
    inputValue: preserveInputValue ? state.inputValue : "",
    isStreaming: false,
    lastInterrupted: false,
    lastSubmittedInput: preserveLastSubmittedInput
      ? state.lastSubmittedInput ?? fallbackLastSubmittedInput
      : null,
    latestDiagnostics: shouldPreserveSnapshotSemantics ? state.latestDiagnostics : derivedDiagnostics.latestDiagnostics,
    latestDiagnosticSummary: shouldPreserveSnapshotSemantics
      ? state.latestDiagnosticSummary
      : derivedDiagnostics.latestDiagnosticSummary,
    messages: normalizeMessages(snapshot.messages),
    pendingRequestMode: null,
    pendingUserInput: null,
    prd,
    prdReview: normalizePrdReview(snapshot.prd_review),
    replayTimeline: normalizeReplayTimeline(snapshot.replay_timeline),
    firstDraft: preserveFirstDraft ? state.firstDraft : nextFirstDraft,
    regenerateRequestId: 0,
    replyGroups: normalizeReplyGroups(snapshot.assistant_reply_groups ?? []),
    selectedHistoryGroupId: null,
    selectedHistoryVersionId: null,
    streamPhase: "idle" as const,
    decisionGuidance: deriveGuidanceFromSnapshot(snapshot),
  };
}

function upsertReplyVersion(
  group: WorkspaceReplyGroup,
  version: WorkspaceReplyVersion,
): WorkspaceReplyGroup {
  const existingIndex = group.versions.findIndex((item) => item.id === version.id);
  if (existingIndex === -1) {
    return {
      ...group,
      versions: [...group.versions, version].sort((a, b) => a.versionNo - b.versionNo),
    };
  }

  return {
    ...group,
    versions: group.versions.map((item, index) =>
      index === existingIndex ? { ...item, ...version } : item,
    ),
  };
}

function extractAssistantDeltaData(
  data: WorkspaceEvent["data"],
): Extract<WorkspaceEvent, { type: "assistant.delta" }>["data"] {
  return data as Extract<WorkspaceEvent, { type: "assistant.delta" }>["data"];
}

function extractAssistantDoneData(
  data: WorkspaceEvent["data"],
): Extract<WorkspaceEvent, { type: "assistant.done" }>["data"] {
  return data as Extract<WorkspaceEvent, { type: "assistant.done" }>["data"];
}

function extractAssistantErrorData(
  data: WorkspaceEvent["data"],
): Extract<WorkspaceEvent, { type: "assistant.error" }>["data"] {
  return data as Extract<WorkspaceEvent, { type: "assistant.error" }>["data"];
}

function createInitialState(): Omit<
  WorkspaceState,
  | "applyEvent"
  | "cancelPendingRequest"
  | "failRequest"
  | "hydrateSession"
  | "refreshSessionSnapshot"
  | "markInterrupted"
  | "resetError"
  | "selectModelConfig"
  | "setAvailableModelConfigs"
  | "setSessionFinalizing"
  | "setInputValue"
  | "setLeftNavCollapsed"
  | "setStreaming"
  | "startRegenerate"
  | "startRequest"
> {
  return {
    activeAssistantVersionId: null,
    activeReplyGroupId: null,
    availableModelConfigs: [],
    collaborationModeLabel: null,
    workflowStage: null,
    isFinalizeReady: false,
    isCompleted: false,
    currentAction: {
      action: "probe_deeper",
      target: "target_user",
      reason: "先把最核心的目标用户讲清楚，后续问题、价值和 MVP 才能持续收敛。",
    },
    currentModelScene: null,
    errorMessage: null,
    diagnosticLedger: [],
    diagnosticLedgerSummary: null,
    isLeftNavCollapsed: false,
    isFinalizingSession: false,
    inputValue: "",
    isStreaming: false,
    lastInterrupted: false,
    lastSubmittedInput: null,
    latestDiagnostics: [],
    latestDiagnosticSummary: null,
    messages: [
      {
        role: "assistant",
        content: "我先不急着写方案。你先告诉我，最想服务的第一类用户是谁？",
      },
    ],
    pendingUserInput: null,
    pendingRequestMode: null,
    prd: createInitialPrdState(),
    prdReview: null,
    replayTimeline: [],
    firstDraft: createInitialFirstDraftState(),
    regenerateRequestId: 0,
    replyGroups: {},
    selectedModelConfigId: null,
    selectedHistoryGroupId: null,
    selectedHistoryVersionId: null,
    streamPhase: "idle",
    decisionGuidance: null,
  };
}

export function createWorkspaceStore() {
  return createStore<WorkspaceState>()((set, get) => ({
    ...createInitialState(),
    applyEvent: (event) =>
      set((state) => {
        switch (event.type) {
          case "message.accepted":
            return {
              ...state,
              lastSubmittedInput: state.pendingUserInput ?? state.lastSubmittedInput,
              messages:
                state.pendingRequestMode === "regenerate" || !state.pendingUserInput
                  ? state.messages
                  : [
                      ...state.messages,
                      {
                        id: event.data.message_id,
                        role: "user",
                        content: state.pendingUserInput,
                        replyGroupId: null,
                        versionNo: null,
                        isLatest: null,
                      },
                    ],
              pendingUserInput: null,
              pendingRequestMode: state.pendingRequestMode === "new" ? null : state.pendingRequestMode,
            };
          case "reply_group.created": {
            const existingGroup = state.replyGroups[event.data.reply_group_id];
            return {
              ...state,
              replyGroups: {
                ...state.replyGroups,
                [event.data.reply_group_id]: {
                  id: event.data.reply_group_id,
                  sessionId: event.data.session_id,
                  userMessageId: event.data.user_message_id,
                  latestVersionId: existingGroup?.latestVersionId ?? null,
                  versions: existingGroup?.versions ?? [],
                },
              },
              selectedHistoryGroupId:
                state.selectedHistoryGroupId ?? event.data.reply_group_id,
            };
          }
          case "action.decided":
            return {
              ...state,
              currentAction: event.data,
            };
          case "decision.ready":
            {
              const latestDiagnostics = normalizeDiagnostics(event.data.diagnostics);
              const diagnosticLedger = mergeDiagnosticLedger(state.diagnosticLedger, latestDiagnostics);
              return {
                ...state,
                decisionGuidance: deriveGuidanceFromDecisionReady(event.data),
                latestDiagnostics,
                latestDiagnosticSummary: normalizeDiagnosticSummary(event.data.diagnostic_summary),
                diagnosticLedger,
                diagnosticLedgerSummary:
                  normalizeDiagnosticSummary(event.data.ledger_summary) ??
                  summarizeDiagnosticLedger(diagnosticLedger),
              };
            }
          case "draft.updated": {
            const data = event.data as DraftUpdatedData;
            const sections: Record<string, FirstDraftSection> = { ...state.firstDraft.sections };
            Object.entries(data.sections ?? {}).forEach(([key, value]) => {
              const section = normalizeFirstDraftSection(value);
              if (section) {
                sections[key] = section;
              }
            });
            const evidenceRegistry = { ...state.firstDraft.evidenceRegistry };
            (Array.isArray(data.evidence_registry) ? data.evidence_registry : []).forEach((item) => {
              const normalized = normalizeFirstDraftEvidence(item);
              if (normalized) {
                evidenceRegistry[normalized.id] = normalized;
              }
            });
            const draftSummary = data.draft_summary && typeof data.draft_summary === "object"
              ? data.draft_summary as Record<string, unknown>
              : {};
            return {
              ...state,
              firstDraft: {
                version: typeof draftSummary.version === "number"
                  ? draftSummary.version
                  : state.firstDraft.version,
                status: state.firstDraft.status,
                sections,
                evidenceRegistry,
                latestUpdates: {
                  version: typeof draftSummary.version === "number"
                    ? draftSummary.version
                    : state.firstDraft.latestUpdates.version,
                  sectionKeys: Array.isArray(draftSummary.section_keys ?? draftSummary.sectionKeys)
                    ? (draftSummary.section_keys ?? draftSummary.sectionKeys as unknown[])
                        .filter((entry): entry is string => typeof entry === "string")
                    : Array.isArray(data.sections_changed)
                      ? data.sections_changed.filter((entry): entry is string => typeof entry === "string")
                      : [],
                  entryIds: Array.isArray(draftSummary.entry_ids ?? draftSummary.entryIds)
                    ? (draftSummary.entry_ids ?? draftSummary.entryIds as unknown[])
                        .filter((entry): entry is string => typeof entry === "string")
                    : Array.isArray(data.entry_ids)
                      ? data.entry_ids.filter((entry): entry is string => typeof entry === "string")
                      : [],
                  evidenceIds: Array.isArray(draftSummary.evidence_ids ?? draftSummary.evidenceIds)
                    ? (draftSummary.evidence_ids ?? draftSummary.evidenceIds as unknown[])
                        .filter((entry): entry is string => typeof entry === "string")
                    : state.firstDraft.latestUpdates.evidenceIds,
                },
              },
            };
          }
          case "assistant.version.started": {
            const existingGroup = state.replyGroups[event.data.reply_group_id] ?? {
              id: event.data.reply_group_id,
              sessionId: event.data.session_id,
              userMessageId: event.data.user_message_id,
              latestVersionId: null,
              versions: [],
            };
            const nextGroup = upsertReplyVersion(existingGroup, {
              id: event.data.assistant_version_id,
              versionNo: event.data.version_no,
              content:
                existingGroup.versions.find((item) => item.id === event.data.assistant_version_id)
                  ?.content ?? "",
              assistantMessageId: event.data.assistant_message_id,
              isRegeneration: event.data.is_regeneration,
              isLatest: false,
            });
            return {
              ...state,
              activeAssistantVersionId: event.data.assistant_version_id,
              activeReplyGroupId: event.data.reply_group_id,
              replyGroups: {
                ...state.replyGroups,
                [event.data.reply_group_id]: nextGroup,
              },
              selectedHistoryGroupId: event.data.reply_group_id,
              selectedHistoryVersionId: event.data.assistant_version_id,
            };
          }
          case "assistant.delta": {
            const deltaData = extractAssistantDeltaData(event.data);
            if ("assistant_version_id" in deltaData) {
              const group = state.replyGroups[deltaData.reply_group_id];
              const existingGroup: WorkspaceReplyGroup = group ?? {
                id: deltaData.reply_group_id,
                sessionId: deltaData.session_id,
                userMessageId: deltaData.user_message_id,
                latestVersionId: null,
                versions: [],
              };
              const existingVersion = existingGroup.versions.find(
                (item) => item.id === deltaData.assistant_version_id,
              );
              const nextGroup = upsertReplyVersion(existingGroup, {
                id: deltaData.assistant_version_id,
                versionNo: deltaData.version_no,
                content: `${existingVersion?.content ?? ""}${deltaData.delta}`,
                assistantMessageId: deltaData.assistant_message_id,
                isRegeneration: deltaData.is_regeneration,
                isLatest: false,
              });

              if (deltaData.is_regeneration) {
                return {
                  ...state,
                  lastInterrupted: false,
                  streamPhase: "streaming",
                  replyGroups: {
                    ...state.replyGroups,
                    [deltaData.reply_group_id]: nextGroup,
                  },
                };
              }

              const lastMessage = state.messages.at(-1);
              const messages: WorkspaceMessage[] =
                lastMessage?.role === "assistant"
                  ? [
                      ...state.messages.slice(0, -1),
                      {
                        ...lastMessage,
                        content: `${lastMessage.content}${deltaData.delta}`,
                        replyGroupId: deltaData.reply_group_id,
                        versionNo: deltaData.version_no,
                        isLatest: false,
                      },
                    ]
                  : [
                      ...state.messages,
                      {
                        role: "assistant",
                        content: deltaData.delta,
                        replyGroupId: deltaData.reply_group_id,
                        versionNo: deltaData.version_no,
                        isLatest: false,
                      },
                    ];

              return {
                ...state,
                messages,
                lastInterrupted: false,
                streamPhase: "streaming",
                replyGroups: {
                  ...state.replyGroups,
                  [deltaData.reply_group_id]: nextGroup,
                },
              };
            }

            const lastMessage = state.messages.at(-1);
            if (lastMessage?.role === "assistant") {
              return {
                ...state,
                messages: [
                  ...state.messages.slice(0, -1),
                  {
                    ...lastMessage,
                    content: `${lastMessage.content}${deltaData.delta}`,
                  },
                ],
                lastInterrupted: false,
                streamPhase: "streaming",
              };
            }

            return {
              ...state,
              messages: [
                ...state.messages,
                {
                  role: "assistant",
                  content: deltaData.delta,
                },
              ],
              lastInterrupted: false,
              streamPhase: "streaming",
            };
          }
          case "assistant.done": {
            const doneData = extractAssistantDoneData(event.data);
            if ("assistant_version_id" in doneData) {
              if (
                state.activeAssistantVersionId &&
                state.activeAssistantVersionId !== doneData.assistant_version_id
              ) {
                return state;
              }
              const group = state.replyGroups[doneData.reply_group_id];
              const existingGroup: WorkspaceReplyGroup = group ?? {
                id: doneData.reply_group_id,
                sessionId: doneData.session_id,
                userMessageId: doneData.user_message_id,
                latestVersionId: null,
                versions: [],
              };
              const latestContent =
                existingGroup.versions.find((item) => item.id === doneData.assistant_version_id)
                  ?.content ?? "";
              const nextGroup = {
                ...existingGroup,
                latestVersionId: doneData.assistant_version_id,
                versions: existingGroup.versions.map((item) =>
                  item.id === doneData.assistant_version_id
                    ? {
                        ...item,
                        assistantMessageId: doneData.assistant_message_id,
                        createdAt: doneData.created_at ?? item.createdAt,
                        isLatest: true,
                      }
                    : { ...item, isLatest: false },
                ),
              };

              const assistantMessageId = doneData.assistant_message_id ?? doneData.message_id;
              let messages = state.messages;
              if (assistantMessageId) {
                const targetIndex = messages.findIndex(
                  (message) =>
                    message.role === "assistant" &&
                    (message.id === assistantMessageId ||
                      message.id === doneData.assistant_version_id ||
                      message.replyGroupId === doneData.reply_group_id),
                );
                if (targetIndex >= 0) {
                  messages = messages.map((message, index) =>
                    index === targetIndex
                      ? {
                          ...message,
                          id: doneData.assistant_version_id,
                          content: latestContent,
                          replyGroupId: doneData.reply_group_id,
                          versionNo: doneData.version_no,
                          isLatest: true,
                        }
                      : message.replyGroupId === doneData.reply_group_id
                        ? { ...message, isLatest: false }
                        : message,
                  );
                } else if (!doneData.is_regeneration) {
                  const lastMessage = messages.at(-1);
                  if (lastMessage?.role === "assistant" && !lastMessage.id) {
                    messages = [
                      ...messages.slice(0, -1),
                      {
                        ...lastMessage,
                        id: doneData.assistant_version_id,
                        content: latestContent,
                        replyGroupId: doneData.reply_group_id,
                        versionNo: doneData.version_no,
                        isLatest: true,
                      },
                    ];
                  } else {
                    messages = [
                      ...messages,
                      {
                        id: doneData.assistant_version_id,
                        role: "assistant",
                        content: latestContent,
                        replyGroupId: doneData.reply_group_id,
                        versionNo: doneData.version_no,
                        isLatest: true,
                      },
                    ];
                  }
                }
              }

              return {
                ...state,
                activeAssistantVersionId: null,
                activeReplyGroupId: null,
                isStreaming: false,
                lastInterrupted: false,
                pendingRequestMode: null,
                pendingUserInput: null,
                streamPhase: "idle",
                messages,
                replyGroups: {
                  ...state.replyGroups,
                  [doneData.reply_group_id]: nextGroup,
                },
                selectedHistoryGroupId: doneData.reply_group_id,
                selectedHistoryVersionId: doneData.assistant_version_id,
              };
            }

            const lastMessage = state.messages.at(-1);
            if (lastMessage?.role !== "assistant") {
              return {
                ...state,
                isStreaming: false,
                lastInterrupted: false,
                pendingRequestMode: null,
                pendingUserInput: null,
                streamPhase: "idle",
              };
            }

            return {
              ...state,
              isStreaming: false,
              lastInterrupted: false,
              pendingRequestMode: null,
              pendingUserInput: null,
              streamPhase: "idle",
              messages: [
                ...state.messages.slice(0, -1),
                {
                  ...lastMessage,
                  id: doneData.message_id,
                },
              ],
            };
          }
          case "assistant.error": {
            const errorData = extractAssistantErrorData(event.data);
            if (
              errorData.assistant_version_id &&
              state.activeAssistantVersionId &&
              state.activeAssistantVersionId !== errorData.assistant_version_id
            ) {
              return state;
            }

            return {
              ...state,
              activeAssistantVersionId: null,
              activeReplyGroupId: null,
              errorMessage: errorData.message,
              isStreaming: false,
              lastInterrupted: false,
              pendingRequestMode: null,
              pendingUserInput: null,
              streamPhase: "idle",
            };
          }
          case "prd.updated": {
            const nextPrd = normalizeIncomingPrdPanelUpdate(state.prd, event.data);
            return {
              ...state,
              prd: nextPrd,
              isFinalizeReady:
                typeof event.data.ready_for_confirmation === "boolean"
                  ? event.data.ready_for_confirmation
                  : state.isFinalizeReady,
            };
          }
          default:
            return state;
        }
      }),
    cancelPendingRequest: () =>
      set((state) => ({
        ...state,
        activeAssistantVersionId: null,
        activeReplyGroupId: null,
        isStreaming: false,
        pendingRequestMode: null,
        pendingUserInput: null,
        streamPhase: "idle",
      })),
    failRequest: (message) =>
      set((state) => ({
        ...state,
        activeAssistantVersionId: null,
        activeReplyGroupId: null,
        errorMessage: message,
        isStreaming: false,
        lastInterrupted: false,
        pendingRequestMode: null,
        pendingUserInput: null,
        streamPhase: "idle",
      })),
    hydrateSession: (snapshot) =>
      set((state) => buildHydratedSessionState(state, snapshot)),
    refreshSessionSnapshot: (snapshot) =>
      set((state) =>
        buildHydratedSessionState(state, snapshot, {
          preserveCurrentAction: true,
          preserveInputValue: true,
          preserveLastSubmittedInput: true,
          preserveFresherPrd: true,
        }),
      ),
    markInterrupted: () =>
      set((state) => ({
        ...state,
        activeAssistantVersionId: null,
        activeReplyGroupId: null,
        isStreaming: false,
        lastInterrupted: true,
        pendingRequestMode: null,
        streamPhase: "idle",
      })),
    resetError: () =>
      set((state) => ({
        ...state,
        errorMessage: null,
      })),
    selectModelConfig: (modelConfigId) =>
      set((state) => ({
        ...state,
        selectedModelConfigId: state.availableModelConfigs.some((item) => item.id === modelConfigId)
          ? modelConfigId
          : state.selectedModelConfigId,
      })),
    setAvailableModelConfigs: (items) =>
      set((state) => {
        const nextSelectedModelId =
          state.selectedModelConfigId && items.some((item) => item.id === state.selectedModelConfigId)
            ? state.selectedModelConfigId
            : items[0]?.id ?? null;

        return {
          ...state,
          availableModelConfigs: items,
          selectedModelConfigId: nextSelectedModelId,
        };
      }),
    setSessionFinalizing: (value) =>
      set((state) => ({
        ...state,
        isFinalizingSession: value,
      })),
    setInputValue: (value) =>
      set((state) => ({
        ...state,
        inputValue: value,
      })),
    setLeftNavCollapsed: (collapsed) =>
      set((state) => ({
        ...state,
        isLeftNavCollapsed: typeof collapsed === "function" ? collapsed(state.isLeftNavCollapsed) : collapsed,
      })),
    setStreaming: (value) =>
      set((state) => ({
        ...state,
        isStreaming: value,
        lastInterrupted: value ? false : state.lastInterrupted,
        pendingRequestMode: value ? state.pendingRequestMode : null,
        streamPhase: value ? state.streamPhase : "idle",
      })),
    startRegenerate: () => {
      const { isStreaming, lastSubmittedInput, pendingRequestMode, selectedModelConfigId } = get();
      if (
        isStreaming ||
        pendingRequestMode === "regenerate" ||
        !lastSubmittedInput ||
        !selectedModelConfigId
      ) {
        return false;
      }

      set((state) => {
        return {
          ...state,
          errorMessage: null,
          isStreaming: true,
          lastInterrupted: false,
          pendingRequestMode: "regenerate",
          pendingUserInput: lastSubmittedInput,
          streamPhase: "waiting",
          regenerateRequestId: state.regenerateRequestId + 1,
        };
      });

      return true;
    },
    startRequest: (content, mode = "new") =>
      set((state) => ({
        ...state,
        activeAssistantVersionId: null,
        activeReplyGroupId: null,
        errorMessage: null,
        inputValue: "",
        isStreaming: true,
        lastInterrupted: false,
        pendingRequestMode: mode,
        pendingUserInput: content,
        streamPhase: "waiting",
      })),
  }));
}

export const workspaceStore = createWorkspaceStore();

export function useWorkspaceStore<T>(selector: (state: WorkspaceState) => T): T {
  return useStore(workspaceStore, selector);
}
