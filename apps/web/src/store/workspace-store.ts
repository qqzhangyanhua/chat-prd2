import { createStore } from "zustand/vanilla";
import { useStore } from "zustand";

import type {
  NextAction,
  PrdState,
  SessionSnapshotResponse,
  WorkspaceEvent,
  WorkspaceMessage,
} from "../lib/types";

type StreamPhase = "idle" | "waiting" | "streaming";

interface WorkspaceState {
  currentAction: NextAction | null;
  errorMessage: string | null;
  inputValue: string;
  isStreaming: boolean;
  messages: WorkspaceMessage[];
  pendingUserInput: string | null;
  prd: PrdState;
  streamPhase: StreamPhase;
  applyEvent: (event: WorkspaceEvent) => void;
  resetError: () => void;
  setInputValue: (value: string) => void;
  setStreaming: (value: boolean) => void;
  startRequest: (content: string) => void;
  failRequest: (message: string) => void;
  hydrateSession: (snapshot: SessionSnapshotResponse) => void;
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

function createInitialState(): Omit<
  WorkspaceState,
  | "applyEvent"
  | "failRequest"
  | "resetError"
  | "setInputValue"
  | "setStreaming"
  | "startRequest"
  | "hydrateSession"
> {
  return {
    currentAction: {
      action: "probe_deeper",
      target: "target_user",
      reason: "先把最核心的目标用户讲清楚，后续问题、价值和 MVP 才能持续收敛。",
    },
    errorMessage: null,
    inputValue: "先说说你现在脑子里最想解决的是谁的什么问题。",
    isStreaming: false,
    messages: [
      {
        role: "assistant",
        content: "我先不急着写方案。你先告诉我，最想服务的第一类用户是谁？",
      },
    ],
    pendingUserInput: null,
    prd: {
      sections: initialPrdSections,
    },
    streamPhase: "idle",
  };
}

export function createWorkspaceStore() {
  return createStore<WorkspaceState>()((set) => ({
    ...createInitialState(),
    applyEvent: (event) =>
      set((state) => {
        switch (event.type) {
          case "message.accepted":
            return {
              ...state,
              messages: state.pendingUserInput
                ? [
                    ...state.messages,
                    {
                      id: event.data.message_id,
                      role: "user",
                      content: state.pendingUserInput,
                    },
                  ]
                : state.messages,
              pendingUserInput: null,
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
              streamPhase: "streaming",
            };
          }
          case "assistant.done": {
            const lastMessage = state.messages.at(-1);
            if (lastMessage?.role !== "assistant") {
              return {
                ...state,
                isStreaming: false,
                streamPhase: "idle",
              };
            }

            return {
              ...state,
              isStreaming: false,
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
    failRequest: (message) =>
      set((state) => ({
        ...state,
        errorMessage: message,
        isStreaming: false,
        pendingUserInput: null,
        streamPhase: "idle",
      })),
    hydrateSession: (snapshot) =>
      set((state) => ({
        ...state,
        currentAction: null,
        errorMessage: null,
        inputValue:
          typeof snapshot.state.idea === "string" ? snapshot.state.idea : state.inputValue,
        isStreaming: false,
        messages: [],
        pendingUserInput: null,
        prd: {
          sections:
            Object.keys(snapshot.prd_snapshot.sections).length > 0
              ? normalizePrdSections(snapshot.prd_snapshot.sections)
              : state.prd.sections,
        },
        streamPhase: "idle",
      })),
    resetError: () =>
      set((state) => ({
        ...state,
        errorMessage: null,
      })),
    setInputValue: (value) =>
      set((state) => ({
        ...state,
        inputValue: value,
      })),
    setStreaming: (value) =>
      set((state) => ({
        ...state,
        isStreaming: value,
        streamPhase: value ? state.streamPhase : "idle",
      })),
    startRequest: (content) =>
      set((state) => ({
        ...state,
        errorMessage: null,
        inputValue: content,
        isStreaming: true,
        pendingUserInput: content,
        streamPhase: "waiting",
      })),
  }));
}

export const workspaceStore = createWorkspaceStore();

export function useWorkspaceStore<T>(selector: (state: WorkspaceState) => T): T {
  return useStore(workspaceStore, selector);
}
