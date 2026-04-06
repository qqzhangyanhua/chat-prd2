import { useStore } from "zustand";
import { createStore } from "zustand/vanilla";

import type {
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

interface WorkspaceState {
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
  regenerateRequestId: number;
  selectedModelConfigId: string | null;
  streamPhase: StreamPhase;
  applyEvent: (event: WorkspaceEvent) => void;
  cancelPendingRequest: () => void;
  failRequest: (message: string) => void;
  hydrateSession: (snapshot: SessionSnapshotResponse) => void;
  markInterrupted: () => void;
  resetError: () => void;
  selectModelConfig: (modelConfigId: string) => void;
  setAvailableModelConfigs: (items: EnabledModelConfigItem[]) => void;
  setInputValue: (value: string) => void;
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

function normalizeMessages(messages: ConversationMessage[]): WorkspaceMessage[] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
    }));
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
  | "setStreaming"
  | "startRegenerate"
  | "startRequest"
> {
  return {
    availableModelConfigs: [],
    currentAction: {
      action: "probe_deeper",
      target: "target_user",
      reason: "先把最核心的目标用户讲清楚，后续问题、价值和 MVP 才能持续收敛。",
    },
    errorMessage: null,
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
      sections: initialPrdSections,
    },
    regenerateRequestId: 0,
    selectedModelConfigId: null,
    streamPhase: "idle",
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
                      },
                    ],
              pendingUserInput: null,
              pendingRequestMode: null,
            };
          case "action.decided":
            return {
              ...state,
              currentAction: event.data,
            };
          case "assistant.delta": {
            const lastMessage = state.messages.at(-1);
            if (lastMessage?.role === "assistant") {
              return {
                ...state,
                messages: [
                  ...state.messages.slice(0, -1),
                  {
                    ...lastMessage,
                    content: `${lastMessage.content}${event.data.delta}`,
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
                  content: event.data.delta,
                },
              ],
              lastInterrupted: false,
              streamPhase: "streaming",
            };
          }
          case "assistant.done": {
            const lastMessage = state.messages.at(-1);
            if (lastMessage?.role !== "assistant") {
              return {
                ...state,
                isStreaming: false,
                lastInterrupted: false,
                streamPhase: "idle",
              };
            }

            return {
              ...state,
              isStreaming: false,
              lastInterrupted: false,
              streamPhase: "idle",
              messages: [
                ...state.messages.slice(0, -1),
                {
                  ...lastMessage,
                  id: event.data.message_id,
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
        isStreaming: false,
        pendingRequestMode: null,
        pendingUserInput: null,
        streamPhase: "idle",
      })),
    failRequest: (message) =>
      set((state) => ({
        ...state,
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
              : state.prd.sections,
        },
        regenerateRequestId: 0,
        streamPhase: "idle",
      })),
    markInterrupted: () =>
      set((state) => ({
        ...state,
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
        const lastMessage = state.messages.at(-1);
        return {
          ...state,
          errorMessage: null,
          isStreaming: true,
          lastInterrupted: false,
          messages:
            lastMessage?.role === "assistant" ? state.messages.slice(0, -1) : state.messages,
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
