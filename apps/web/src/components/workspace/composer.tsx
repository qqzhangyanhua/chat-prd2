"use client";

import { sendMessage } from "../../lib/api";
import { parseEventStream } from "../../lib/sse";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { useWorkspaceStore, workspaceStore } from "../../store/workspace-store";

interface ComposerProps {
  sessionId: string;
}

export function Composer({ sessionId }: ComposerProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);
  const errorMessage = useWorkspaceStore((state) => state.errorMessage);
  const inputValue = useWorkspaceStore((state) => state.inputValue);
  const isStreaming = useWorkspaceStore((state) => state.isStreaming);
  const streamPhase = useWorkspaceStore((state) => state.streamPhase);
  const resetError = useWorkspaceStore((state) => state.resetError);
  const setInputValue = useWorkspaceStore((state) => state.setInputValue);

  async function handleSend() {
    const content = inputValue.trim();
    if (!content || isStreaming) {
      return;
    }

    workspaceStore.getState().startRequest(content);

    try {
      const stream = await sendMessage(sessionId, content, accessToken);
      for await (const event of parseEventStream(stream)) {
        workspaceStore.getState().applyEvent(event);
      }
      if (workspaceStore.getState().isStreaming) {
        workspaceStore.getState().setStreaming(false);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "消息发送失败";
      workspaceStore.getState().failRequest(message);
      showToast({
        id: `send-message-${sessionId}`,
        message,
        tone: "error",
      });
    }
  }

  const statusMessage =
    streamPhase === "waiting"
      ? "正在等待智能体回应..."
      : streamPhase === "streaming"
        ? "正在生成回复..."
        : "优先用选择推进，必要时再补自由输入。";

  return (
    <form
      className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="block">
        <span className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
          当前输入
        </span>
        <textarea
          className="mt-3 min-h-32 w-full resize-none rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4 text-sm leading-7 text-stone-800 outline-none transition focus:border-stone-900"
          onChange={(event) => {
            resetError();
            setInputValue(event.target.value);
          }}
          placeholder="补充你的目标用户、真实场景、当前做法，或者直接回答上一轮问题。"
          value={inputValue}
        />
      </label>

      <div className="mt-4 flex items-center justify-between gap-4">
        <div className="space-y-1">
          <p className="text-sm text-stone-500">{statusMessage}</p>
          {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}
        </div>
        <button
          className="rounded-2xl bg-stone-900 px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-stone-400"
          disabled={isStreaming}
          onClick={() => void handleSend()}
          type="button"
        >
          {isStreaming ? "发送中..." : "发送消息"}
        </button>
      </div>
    </form>
  );
}
