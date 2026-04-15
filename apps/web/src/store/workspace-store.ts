import { useStore } from "zustand";
import { createStore } from "zustand/vanilla";

import type {
  AgentTurnDecision,
  DecisionGuidance,
  DecisionStrategy,
  AssistantReplyGroup,
  AssistantReplyVersion,
  ConversationMessage,
  EnabledModelConfigItem,
  NextAction,
  PrdState,
  RecommendedScene,
  SessionSnapshotResponse,
  StateSnapshotResponse,
  SuggestionOption,
  WorkflowStage,
  WorkspaceEvent,
  WorkspaceMessage,
} from "../lib/types";
import {
  createInitialExtraPrdSections,
  createInitialPrdMeta,
  createInitialPrdSections,
  deriveExtraPrdSections,
  derivePrimaryPrdSections,
  derivePrdMeta,
  normalizeIncomingPrdSections,
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
  inputValue: string;
  isFinalizingSession: boolean;
  isStreaming: boolean;
  lastInterrupted: boolean;
  lastSubmittedInput: string | null;
  messages: WorkspaceMessage[];
  pendingUserInput: string | null;
  pendingRequestMode: RequestMode | null;
  prd: PrdState;
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
): boolean {
  const currentVersion = current.prd.meta.draftVersion;
  const prdDraft = nextState.prd_draft;
  const nextVersion =
    prdDraft && typeof prdDraft === "object" && typeof prdDraft.version === "number"
      ? prdDraft.version
      : null;

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
  const strategyReason =
    judgementMeta?.strategy_reason ?? decision.state_patch_json?.strategy_reason ?? null;

  const metaNextQuestions = nextStepMeta?.next_best_questions;
  const fallbackNextQuestions = decision.state_patch_json?.next_best_questions;
  const nextBestQuestions = normalizeBestQuestions(metaNextQuestions ?? fallbackNextQuestions);
  const confirmQuickReplies = normalizeBestQuestions(nextStepMeta?.confirm_quick_replies);
  const suggestionOptions = normalizeSuggestionOptions(nextStepMeta?.suggestion_options);

  if (!nextBestQuestions.length && !suggestionOptions.length) {
    return null;
  }

  return {
    conversationStrategy,
    strategyLabel,
    strategyReason,
    nextBestQuestions,
    confirmQuickReplies,
    ...(suggestionOptions.length ? { suggestionOptions } : {}),
  };
}

function deductionStrategyFromState(statePatch?: AgentTurnDecision["state_patch_json"]): string | undefined {
  return statePatch?.conversation_strategy;
}

function mapStrategy(value?: string): DecisionStrategy {
  if (!value) {
    return "clarify";
  }
  if (value === "greet" || value === "clarify" || value === "choose" || value === "converge" || value === "confirm") {
    return value;
  }
  return "clarify";
}

function deriveGuidanceFromSnapshot(snapshot: SessionSnapshotResponse): DecisionGuidance | null {
  const latest = pickLatestDecision(snapshot.turn_decisions ?? []);
  if (!latest) {
    return null;
  }

  return deriveDecisionGuidance(latest);
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
  const nextPrd: PrdState = {
    extraSections: deriveExtraPrdSections(snapshot.state),
    meta: derivePrdMeta(snapshot.state),
    sections: derivePrimaryPrdSections(snapshot.state, snapshot.prd_snapshot.sections),
  };
  const preserveByPrdVersion = preserveFresherPrd && shouldPreserveCurrentPrd(state.prd, nextPrd);
  const preserveByWorkflowSemantics = preserveFresherPrd && isSnapshotOlderByDraftVersion(state, snapshot.state);
  const shouldPreserveSnapshotSemantics = preserveByPrdVersion || preserveByWorkflowSemantics;
  const workflowFlags = shouldPreserveSnapshotSemantics
    ? {
        workflowStage: state.workflowStage,
        isFinalizeReady: state.isFinalizeReady,
        isCompleted: state.isCompleted,
      }
    : deriveWorkflowFlags(snapshot.state);
  const prd = preserveByPrdVersion ? state.prd : nextPrd;

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
    inputValue: preserveInputValue ? state.inputValue : "",
    isStreaming: false,
    lastInterrupted: false,
    lastSubmittedInput: preserveLastSubmittedInput
      ? state.lastSubmittedInput ?? fallbackLastSubmittedInput
      : null,
    messages: normalizeMessages(snapshot.messages),
    pendingRequestMode: null,
    pendingUserInput: null,
    prd,
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
    isLeftNavCollapsed: false,
    isFinalizingSession: false,
    inputValue: "",
    isStreaming: false,
    lastInterrupted: false,
    lastSubmittedInput: null,
    messages: [
      {
        role: "assistant",
        content: "我先不急着写方案。你先告诉我，最想服务的第一类用户是谁？",
      },
    ],
    pendingUserInput: null,
    pendingRequestMode: null,
    prd: {
      extraSections: createInitialExtraPrdSections(),
      meta: createInitialPrdMeta(),
      sections: createInitialPrdSections(),
    },
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
            const normalizedPrdUpdate = normalizeIncomingPrdSections(event.data.sections);
            return {
              ...state,
              prd: {
                ...state.prd,
                meta: event.data.meta ?? state.prd.meta,
                sections: {
                  ...state.prd.sections,
                  ...normalizedPrdUpdate.sections,
                },
                extraSections: {
                  ...state.prd.extraSections,
                  ...normalizedPrdUpdate.extraSections,
                },
              },
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
