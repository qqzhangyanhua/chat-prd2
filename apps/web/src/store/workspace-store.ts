import { createStore } from "zustand/vanilla";
import { useStore } from "zustand";

import type { NextAction, PrdState, WorkspaceEvent, WorkspaceMessage } from "../lib/types";


interface WorkspaceState {
  currentAction: NextAction | null;
  errorMessage: string | null;
  inputValue: string;
  isStreaming: boolean;
  messages: WorkspaceMessage[];
  pendingUserInput: string | null;
  prd: PrdState;
  applyEvent: (event: WorkspaceEvent) => void;
  resetError: () => void;
  setInputValue: (value: string) => void;
  setStreaming: (value: boolean) => void;
  startRequest: (content: string) => void;
  failRequest: (message: string) => void;
}


const initialPrdSections: PrdState["sections"] = {
  target_user: {
    title: "目标用户",
    content: "已经聚焦到方向模糊、需要被追问和收敛的独立开发者。",
    status: "confirmed",
  },
  problem: {
    title: "核心问题",
    content: "他们能描述很多想法，但说不清核心问题、用户和优先级。",
    status: "inferred",
  },
  solution: {
    title: "解决方案",
    content: "通过结构化提问、挑战和选项推进，把模糊想法收敛成可执行 PRD。",
    status: "inferred",
  },
  mvp_scope: {
    title: "MVP 范围",
    content: "还没有正式框定 MVP，需要继续通过对话收敛。",
    status: "missing",
  },
};


function createInitialState(): Omit<
  WorkspaceState,
  | "applyEvent"
  | "failRequest"
  | "resetError"
  | "setInputValue"
  | "setStreaming"
  | "startRequest"
> {
  return {
    currentAction: {
      action: "probe_deeper",
      target: "target_user",
      reason: "当前还不清楚目标用户是谁，需要继续追问。",
    },
    errorMessage: null,
    inputValue: "我想先聚焦那些已经开始做产品，但一直说不清目标用户是谁的独立开发者。",
    isStreaming: false,
    messages: [
      {
        role: "assistant",
        content: "你现在想做的是一个能陪用户反复梳理产品方向的智能体，而不是一次性写完文档的 PRD 生成器。",
      },
    ],
    pendingUserInput: null,
    prd: {
      sections: initialPrdSections,
    },
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
            };
          }
          case "assistant.done": {
            const lastMessage = state.messages.at(-1);
            if (lastMessage?.role !== "assistant") {
              return {
                ...state,
                isStreaming: false,
              };
            }

            return {
              ...state,
              isStreaming: false,
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
      })),
    startRequest: (content) =>
      set((state) => ({
        ...state,
        errorMessage: null,
        inputValue: content,
        isStreaming: true,
        pendingUserInput: content,
      })),
  }));
}


export const workspaceStore = createWorkspaceStore();


export function useWorkspaceStore<T>(selector: (state: WorkspaceState) => T): T {
  return useStore(workspaceStore, selector);
}
