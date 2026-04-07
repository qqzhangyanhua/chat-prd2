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
  SessionSnapshotResponse,
  WorkspaceEvent,
  WorkspaceMessage,
} from "../lib/types";

type StreamPhase = "idle" | "waiting" | "streaming";
type RequestMode = "new" | "regenerate";

interface WorkspaceReplyVersion {
  assistantMessageId: string | null;
  content: string;
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
  currentAction: NextAction | null;
  errorMessage: string | null;
  inputValue: string;
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
  markInterrupted: () => void;
  resetError: () => void;
  selectModelConfig: (modelConfigId: string) => void;
  setAvailableModelConfigs: (items: EnabledModelConfigItem[]) => void;
  isLeftNavCollapsed: boolean;
  setInputValue: (value: string) => void;
  setLeftNavCollapsed: (collapsed: boolean | ((prev: boolean) => boolean)) => void;
  setStreaming: (value: boolean) => void;
  startRegenerate: () => boolean;
  startRequest: (content: string, mode?: RequestMode) => void;
}

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

function createInitialPrdSections(): PrdState["sections"] {
  return {
    target_user: { ...initialPrdSections.target_user },
    problem: { ...initialPrdSections.problem },
    solution: { ...initialPrdSections.solution },
    mvp_scope: { ...initialPrdSections.mvp_scope },
  };
}

function normalizePrdSections(
  sections: SessionSnapshotResponse["prd_snapshot"]["sections"],
): PrdState["sections"] {
  const normalizedEntries = Object.entries(sections).map(([key, value]) => {
    const content = typeof value.content === "string" ? value.content : "";
    const title = typeof value.title === "string" && value.title ? value.title : key;
    const status =
      value.status === "confirmed" ||
      value.status === "inferred" ||
      value.status === "missing"
        ? value.status
        : "missing";

    return [key, { content, title, status }] as const;
  });

  return Object.fromEntries(normalizedEntries);
}

const STRATEGY_LABEL_MAP: Record<DecisionStrategy, string> = {
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

  if (!nextBestQuestions.length) {
    return null;
  }

  return {
    conversationStrategy,
    strategyLabel,
    strategyReason,
    nextBestQuestions,
  };
}

function deductionStrategyFromState(statePatch?: AgentTurnDecision["state_patch_json"]): string | undefined {
  return statePatch?.conversation_strategy;
}

function mapStrategy(value?: string): DecisionStrategy {
  if (!value) {
    return "clarify";
  }
  if (value === "clarify" || value === "choose" || value === "converge" || value === "confirm") {
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
            assistantMessageId: null,
            isRegeneration: version.version_no > 1,
            isLatest: version.is_latest ?? version.id === group.latest_version_id,
          })),
      },
    ]),
  );
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

function createInitialState(): Omit<
  WorkspaceState,
  | "applyEvent"
  | "cancelPendingRequest"
  | "failRequest"
  | "hydrateSession"
  | "markInterrupted"
  | "resetError"
  | "selectModelConfig"
  | "setAvailableModelConfigs"
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
    currentAction: {
      action: "probe_deeper",
      target: "target_user",
      reason: "先把最核心的目标用户讲清楚，后续问题、价值和 MVP 才能持续收敛。",
    },
    errorMessage: null,
    isLeftNavCollapsed: false,
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
          case "prd.updated":
            return {
              ...state,
              prd: {
                ...state.prd,
                sections: {
                  ...state.prd.sections,
                  ...event.data.sections,
                },
              },
            };
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
      set((state) => ({
        ...state,
        activeAssistantVersionId: null,
        activeReplyGroupId: null,
        currentAction: null,
        errorMessage: null,
        inputValue: "",
        isStreaming: false,
        lastInterrupted: false,
        lastSubmittedInput: null,
        messages: normalizeMessages(snapshot.messages),
        pendingRequestMode: null,
        pendingUserInput: null,
        prd: {
          sections:
            Object.keys(snapshot.prd_snapshot.sections).length > 0
              ? normalizePrdSections(snapshot.prd_snapshot.sections)
              : createInitialPrdSections(),
        },
        regenerateRequestId: 0,
        replyGroups: normalizeReplyGroups(snapshot.assistant_reply_groups ?? []),
        selectedHistoryGroupId: null,
        selectedHistoryVersionId: null,
        streamPhase: "idle",
        decisionGuidance: deriveGuidanceFromSnapshot(snapshot),
      })),
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
      const { lastSubmittedInput, selectedModelConfigId } = get();
      if (!lastSubmittedInput || !selectedModelConfigId) {
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
