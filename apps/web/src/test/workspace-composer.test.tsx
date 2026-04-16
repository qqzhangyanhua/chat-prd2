import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationPanel } from "../components/workspace/conversation-panel";
import { Composer } from "../components/workspace/composer";
import { PrdPanel } from "../components/workspace/prd-panel";
import { finalizeSession, getSession, regenerateMessage, sendMessage } from "../lib/api";
import { useToastStore } from "../store/toast-store";
import { workspaceStore } from "../store/workspace-store";
import type { DecisionGuidance, SessionSnapshotResponse } from "../lib/types";

vi.mock("../lib/api", () => ({
  sendMessage: vi.fn(),
  regenerateMessage: vi.fn(),
  getSession: vi.fn(),
  finalizeSession: vi.fn(),
}));

function createSessionSnapshot(
  overrides: Partial<SessionSnapshotResponse> = {},
): SessionSnapshotResponse {
  return {
    session: {
      id: "demo-session",
      user_id: "user-1",
      title: "AI Co-founder",
      initial_idea: "idea",
      created_at: "2026-04-05T00:00:00Z",
      updated_at: "2026-04-05T00:00:00Z",
    },
    state: {
      idea: "idea",
      stage_hint: "明确问题",
    },
    prd_snapshot: {
      sections: {},
    },
    messages: [],
    assistant_reply_groups: [],
    turn_decisions: [],
    ...overrides,
  };
}

function normalizeMessagesForTest(
  messages: SessionSnapshotResponse["messages"],
) {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    replyGroupId: message.reply_group_id ?? null,
    versionNo: message.version_no ?? null,
    isLatest: message.is_latest ?? null,
  }));
}

beforeEach(() => {
  vi.mocked(getSession).mockReset();
  vi.mocked(getSession).mockResolvedValue(createSessionSnapshot());
});

describe("Composer", () => {
  beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    vi.mocked(regenerateMessage).mockReset();
    vi.mocked(finalizeSession).mockReset();
    useToastStore.getState().clearToast();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
    workspaceStore.getState().setAvailableModelConfigs([
      {
        id: "model-openai",
        name: "OpenAI GPT-4.1",
        model: "gpt-4.1",
      },
      {
        id: "model-anthropic",
        name: "Anthropic Claude 3.7",
        model: "claude-3-7-sonnet",
      },
    ]);
    workspaceStore.getState().setInputValue("请帮我梳理目标用户。");
  });

  it("releases the streaming lock when the sse stream ends without assistant.done", async () => {
    const encoder = new TextEncoder();
    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: message.accepted\ndata: {"message_id":"user-1"}\n\n' +
                'event: assistant.delta\ndata: {"delta":"先收敛 MVP。"}\n\n',
            ),
          );
          controller.close();
        },
      }),
    );

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => {
      expect(workspaceStore.getState().isStreaming).toBe(false);
    });
    expect(screen.getByText("准备好继续，补充你的想法")).toBeInTheDocument();
  });

  it("shows waiting and generating statuses while sending", async () => {
    const encoder = new TextEncoder();
    const controllerActions: Array<() => void> = [];

    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode('event: message.accepted\ndata: {"message_id":"user-1"}\n\n'),
          );
          controllerActions.push(() => {
            controller.enqueue(
              encoder.encode('event: assistant.delta\ndata: {"delta":"继续展开这个想法。"}\n\n'),
            );
            controller.close();
          });
        },
      }),
    );

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(await screen.findByText("等待回应...")).toBeInTheDocument();

    expect(controllerActions).toHaveLength(1);
    controllerActions[0]!();

    expect(await screen.findByText("正在生成回复...")).toBeInTheDocument();
  });

  it("cancels the in-flight stream and restores the idle composer state", async () => {
    let capturedSignal: AbortSignal | undefined;

    vi.mocked(sendMessage).mockImplementation(async (_sessionId, _content, _token, signal) => {
      capturedSignal = signal;
      return new Promise<ReadableStream<Uint8Array>>((_, reject) => {
        signal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        });
      });
    });

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    const stopButton = await screen.findByRole("button", { name: "停止生成" });
    fireEvent.click(stopButton);

    await waitFor(() => {
      expect(workspaceStore.getState().isStreaming).toBe(false);
    });

    expect(capturedSignal?.aborted).toBe(true);
    expect(screen.getByText("准备好继续，补充你的想法")).toBeInTheDocument();
  });

  it("shows an info toast when the user cancels generation", async () => {
    vi.mocked(sendMessage).mockImplementation(async (_sessionId, _content, _token, signal) => {
      return new Promise<ReadableStream<Uint8Array>>((_, reject) => {
        signal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        });
      });
    });

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    fireEvent.click(await screen.findByRole("button", { name: "停止生成" }));

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("已停止本轮生成");
    });

    expect(useToastStore.getState().toast?.tone).toBe("info");
  });

  it("does not show an error toast when the user cancels generation", async () => {
    vi.mocked(sendMessage).mockImplementation(async (_sessionId, _content, _token, signal) => {
      return new Promise<ReadableStream<Uint8Array>>((_, reject) => {
        signal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        });
      });
    });

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    fireEvent.click(await screen.findByRole("button", { name: "停止生成" }));

    await waitFor(() => {
      expect(workspaceStore.getState().isStreaming).toBe(false);
    });

    expect(useToastStore.getState().toast?.tone).not.toBe("error");
    expect(screen.queryByText("消息发送失败")).not.toBeInTheDocument();
  });

  it("shows a global toast when sending a message fails", async () => {
    vi.mocked(sendMessage).mockRejectedValue(new Error("消息发送失败"));

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("消息发送失败");
    });

    expect(await screen.findByText("消息发送失败")).toBeInTheDocument();
  });

  it("switches to the recommended model when model selection is required", async () => {
    vi.mocked(sendMessage).mockRejectedValue(
      Object.assign(new Error("当前模型不可用，请选择其他模型后重试"), {
        code: "MODEL_CONFIG_DISABLED",
        details: {
          recommended_model_config_id: "model-anthropic",
          recommended_model_name: "Anthropic Claude 3.7",
          requested_model_config_id: "model-openai",
        },
        recoveryAction: {
          type: "select_available_model",
          label: "选择可用模型",
          target: null,
        },
      }),
    );

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    const actionButton = await screen.findByRole("button", { name: "切换到 Anthropic Claude 3.7" });
    fireEvent.click(actionButton);

    expect(screen.getByLabelText("选择模型")).toHaveValue("model-anthropic");
    expect(screen.queryByText("当前模型不可用，请选择其他模型后重试")).not.toBeInTheDocument();
  });

  it("offers an immediate retry after switching to the recommended model", async () => {
    const encoder = new TextEncoder();
    vi.mocked(sendMessage)
      .mockRejectedValueOnce(
        Object.assign(new Error("当前模型不可用，请选择其他模型后重试"), {
          code: "MODEL_CONFIG_DISABLED",
          details: {
            recommended_model_config_id: "model-anthropic",
            recommended_model_scene: "reasoning",
            recommended_model_name: "Anthropic Claude 3.7",
            recommended_model_reason: "它更适合继续长文本推理，建议优先切到这个模型继续。",
            requested_model_config_id: "model-openai",
          },
          recoveryAction: {
            type: "select_available_model",
            label: "选择可用模型",
            target: null,
          },
        }),
      )
      .mockResolvedValueOnce(
        new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(
              encoder.encode('event: message.accepted\ndata: {"message_id":"user-2"}\n\n'),
            );
            controller.close();
          },
        }),
      );

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    fireEvent.click(await screen.findByRole("button", { name: "切换到 Anthropic Claude 3.7" }));
    expect(
      await screen.findByText(
        "已切换到 Anthropic Claude 3.7。按当前对话场景优先推荐：长文本推理。它更适合继续长文本推理，建议优先切到这个模型继续。",
      ),
    ).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "立即重试刚才的消息" }));

    await waitFor(() => {
      expect(sendMessage).toHaveBeenNthCalledWith(
        2,
        "demo-session",
        "请帮我梳理目标用户。",
        null,
        expect.any(AbortSignal),
        "model-anthropic",
      );
    });
  });

  it("passes the selected model_config_id when sending a message", async () => {
    const encoder = new TextEncoder();
    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode('event: message.accepted\ndata: {"message_id":"user-1"}\n\n'),
          );
          controller.close();
        },
      }),
    );

    render(<Composer sessionId="demo-session" />);

    fireEvent.change(screen.getByLabelText("选择模型"), {
      target: { value: "model-anthropic" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => {
      expect(sendMessage).toHaveBeenCalledWith(
        "demo-session",
        "请帮我梳理目标用户。",
        null,
        expect.any(AbortSignal),
        "model-anthropic",
      );
    });
  });

  it("disables sending and shows a clear prompt when no model is available", () => {
    workspaceStore.setState(workspaceStore.getInitialState(), true);
    workspaceStore.getState().setInputValue("请帮我梳理目标用户。");

    render(<Composer sessionId="demo-session" />);

    expect(screen.getByText("当前暂无可用模型，请联系管理员配置。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送消息" })).toBeDisabled();
  });

  it("refreshes the workspace from the latest snapshot after sending completes", async () => {
    const snapshot = createSessionSnapshot({
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请帮我梳理目标用户。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "这是最新的生成回复。",
          message_type: "text",
          reply_group_id: null,
          version_no: 1,
          is_latest: true,
        },
      ],
    });

    vi.mocked(getSession).mockResolvedValueOnce(snapshot);
    const encoder = new TextEncoder();
    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: message.accepted\ndata: {"message_id":"user-1"}\n\n' +
                'event: assistant.delta\ndata: {"delta":"先收敛 MVP。"}\n\n',
            ),
          );
          controller.close();
        },
      }),
    );

    render(<Composer sessionId="demo-session" />);
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => {
      expect(vi.mocked(getSession)).toHaveBeenCalledWith("demo-session", null);
    });
    expect(workspaceStore.getState().messages).toEqual(
      normalizeMessagesForTest(snapshot.messages),
    );
  });
});

describe("ConversationPanel empty state", () => {
  beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    vi.mocked(regenerateMessage).mockReset();
    vi.mocked(finalizeSession).mockReset();
    useToastStore.getState().clearToast();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
  });

  it("shows empty state when no messages and not streaming", () => {
    render(<ConversationPanel sessionId="session-1" />);

    expect(screen.getByText(/开始描述你的想法/i)).toBeInTheDocument();
  });
});

describe("ConversationPanel status and history", () => {
  beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    vi.mocked(regenerateMessage).mockReset();
    vi.mocked(finalizeSession).mockReset();
    useToastStore.getState().clearToast();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
    workspaceStore.getState().setAvailableModelConfigs([
      {
        id: "model-openai",
        name: "OpenAI GPT-4.1",
        model: "gpt-4.1",
      },
    ]);
  });

  it("shows a finalized badge instead of the hardcoded ongoing label when workflow is completed", () => {
    workspaceStore.getState().hydrateSession(createSessionSnapshot({
      state: {
        workflow_stage: "completed",
        prd_draft: {
          version: 4,
          status: "finalized",
        },
        finalization_ready: true,
        critic_result: {
          overall_verdict: "pass",
        },
      },
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请整理最终版本。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "这是最终整理后的 PRD 版本。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
      assistant_reply_groups: [
        {
          id: "group-1",
          session_id: "demo-session",
          user_message_id: "user-1",
          latest_version_id: "version-1",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
          versions: [
            {
              id: "version-1",
              reply_group_id: "group-1",
              session_id: "demo-session",
              user_message_id: "user-1",
              version_no: 1,
              content: "这是最终整理后的 PRD 版本。",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 4,
              created_at: "2026-04-05T00:00:00Z",
              is_latest: true,
            },
          ],
        },
      ],
    }));

    render(<ConversationPanel sessionId="demo-session" />);

    expect(screen.getByText("已生成终稿")).toBeInTheDocument();
    expect(screen.queryByText("持续引导中")).not.toBeInTheDocument();
  });

  it("shows completed reminder in the main conversation area", () => {
    workspaceStore.getState().hydrateSession(createSessionSnapshot({
      state: {
        workflow_stage: "completed",
        prd_draft: {
          version: 4,
          status: "finalized",
        },
        finalization_ready: true,
      },
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请整理最终版本。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "这是最终整理后的 PRD 版本。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
    }));

    render(<ConversationPanel sessionId="demo-session" />);

    expect(screen.getByText("已生成最终版，继续输入会重新打开编辑流程。")).toBeInTheDocument();
  });

  it("finalizes by button and refreshes snapshot from server", async () => {
    const completedSnapshot = createSessionSnapshot({
      state: {
        workflow_stage: "completed",
        prd_draft: {
          version: 4,
          status: "finalized",
        },
        finalization_ready: true,
      },
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请整理最终版本。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "这是最终整理后的 PRD 版本。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
    });
    workspaceStore.getState().hydrateSession(createSessionSnapshot({
      state: {
        workflow_stage: "finalize",
        finalization_ready: true,
        prd_draft: {
          version: 3,
          status: "review_ready",
        },
      },
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请整理最终版本。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "当前信息已齐备，可以生成最终版。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
    }));
    vi.mocked(finalizeSession).mockResolvedValueOnce(completedSnapshot);

    render(<ConversationPanel sessionId="demo-session" />);
    fireEvent.click(screen.getByRole("button", { name: "生成最终版 PRD" }));

    await waitFor(() => {
      expect(finalizeSession).toHaveBeenCalledWith(
        "demo-session",
        { confirmation_source: "button" },
        null,
      );
    });
    expect(useToastStore.getState().toast?.tone).toBe("success");
    expect(useToastStore.getState().toast?.message).toContain("最终版");
  });

  it("shares finalize pending state across both finalize entry points", async () => {
    let resolveFinalize!: (value: SessionSnapshotResponse) => void;

    workspaceStore.getState().hydrateSession(createSessionSnapshot({
      state: {
        workflow_stage: "finalize",
        finalization_ready: true,
        prd_draft: {
          version: 3,
          status: "review_ready",
        },
      },
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请整理最终版本。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "当前信息已齐备，可以生成最终版。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
    }));
    vi.mocked(finalizeSession).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFinalize = resolve;
        }),
    );

    render(
      <>
        <ConversationPanel sessionId="demo-session" />
        <PrdPanel sessionId="demo-session" />
      </>,
    );

    const finalizeButtons = screen.getAllByRole("button", { name: "生成最终版 PRD" });
    fireEvent.click(finalizeButtons[0]);

    await waitFor(() => {
      expect(finalizeSession).toHaveBeenCalledTimes(1);
    });

    const disabledButtons = screen.getAllByRole("button", { name: "整理中..." });
    expect(disabledButtons).toHaveLength(2);
    expect(disabledButtons[0]).toBeDisabled();
    expect(disabledButtons[1]).toBeDisabled();

    fireEvent.click(disabledButtons[1]);
    expect(finalizeSession).toHaveBeenCalledTimes(1);

    resolveFinalize(createSessionSnapshot({
      state: {
        workflow_stage: "completed",
        finalization_ready: true,
        prd_draft: {
          version: 4,
          status: "finalized",
        },
      },
    }));

    await waitFor(() => {
      expect(workspaceStore.getState().isFinalizingSession).toBe(false);
    });
  });

  it("disables finalize entry points while a reply is streaming", () => {
    workspaceStore.getState().hydrateSession(createSessionSnapshot({
      state: {
        workflow_stage: "finalize",
        finalization_ready: true,
        prd_draft: {
          version: 3,
          status: "review_ready",
        },
      },
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请整理最终版本。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "当前信息已齐备，可以生成最终版。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
    }));
    workspaceStore.getState().setStreaming(true);

    render(
      <>
        <ConversationPanel sessionId="demo-session" />
        <PrdPanel sessionId="demo-session" />
      </>,
    );

    const finalizeButtons = screen.getAllByRole("button", { name: "生成最终版 PRD" });
    expect(finalizeButtons).toHaveLength(2);
    expect(finalizeButtons[0]).toBeDisabled();
    expect(finalizeButtons[1]).toBeDisabled();
  });

  it("shows reply version timestamps in the history dialog", () => {
    workspaceStore.getState().hydrateSession(createSessionSnapshot({
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请帮我梳理目标用户。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-2",
          session_id: "demo-session",
          role: "assistant",
          content: "第二版回复",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 2,
          is_latest: true,
        },
      ],
      assistant_reply_groups: [
        {
          id: "group-1",
          session_id: "demo-session",
          user_message_id: "user-1",
          latest_version_id: "version-2",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
          versions: [
            {
              id: "version-1",
              reply_group_id: "group-1",
              session_id: "demo-session",
              user_message_id: "user-1",
              version_no: 1,
              content: "第一版回复",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 2,
              created_at: "2026-04-05 10:00",
              is_latest: false,
            },
            {
              id: "version-2",
              reply_group_id: "group-1",
              session_id: "demo-session",
              user_message_id: "user-1",
              version_no: 2,
              content: "第二版回复",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 3,
              created_at: "2026-04-05 10:30",
              is_latest: true,
            },
          ],
        },
      ],
    }));

    render(<ConversationPanel sessionId="demo-session" />);
    fireEvent.click(screen.getByRole("button", { name: "重新生成历史" }));

    const dialog = screen.getByRole("dialog", { name: "重新生成历史" });
    expect(within(dialog).getAllByText("2026-04-05 10:30")).toHaveLength(2);
    expect(within(dialog).getByText("2026-04-05 10:00")).toBeInTheDocument();
  });
});

describe("ConversationPanel regenerate", () => {
  beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    vi.mocked(regenerateMessage).mockReset();
    useToastStore.getState().clearToast();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
    workspaceStore.getState().setAvailableModelConfigs([
      {
        id: "model-openai",
        name: "OpenAI GPT-4.1",
        model: "gpt-4.1",
      },
    ]);
  });

  it("replays the latest accepted input without adding a duplicate user message", async () => {
    const encoder = new TextEncoder();
    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: message.accepted\ndata: {"message_id":"user-1","session_id":"demo-session"}\n\n' +
                'event: reply_group.created\ndata: {"reply_group_id":"group-1","user_message_id":"user-1","session_id":"demo-session","is_regeneration":false,"is_latest":false}\n\n' +
                'event: assistant.version.started\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-1","version_no":1,"assistant_message_id":null,"model_config_id":"model-openai","is_regeneration":false,"is_latest":false}\n\n' +
                'event: assistant.delta\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-1","version_no":1,"assistant_message_id":null,"model_config_id":"model-openai","delta":"先把问题范围说清楚。","is_regeneration":false,"is_latest":false}\n\n' +
                'event: assistant.done\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-1","version_id":"version-1","version_no":1,"assistant_message_id":"assistant-1","model_config_id":"model-openai","prd_snapshot_version":2,"is_regeneration":false,"is_latest":true}\n\n',
            ),
          );
          controller.close();
        },
      }),
    );
    vi.mocked(regenerateMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: action.decided\ndata: {"action":"probe_deeper","target":"target_user","reason":"继续追问"}\n\n' +
                'event: assistant.version.started\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-2","version_no":2,"assistant_message_id":"assistant-1","model_config_id":"model-openai","is_regeneration":true,"is_latest":false}\n\n' +
                'event: assistant.delta\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-2","version_no":2,"assistant_message_id":"assistant-1","model_config_id":"model-openai","delta":"重新生成后的回复。","is_regeneration":true,"is_latest":false}\n\n' +
                'event: assistant.done\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-2","version_id":"version-2","version_no":2,"assistant_message_id":"assistant-1","model_config_id":"model-openai","prd_snapshot_version":3,"is_regeneration":true,"is_latest":true}\n\n',
            ),
          );
          controller.close();
        },
      }),
    );

    const postSendSnapshot = createSessionSnapshot({
      assistant_reply_groups: [
        {
          id: "group-1",
          session_id: "demo-session",
          user_message_id: "user-1",
          latest_version_id: "version-1",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
          versions: [
            {
              id: "version-1",
              reply_group_id: "group-1",
              session_id: "demo-session",
              user_message_id: "user-1",
              version_no: 1,
              content: "先把问题范围说清楚。",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 2,
              created_at: "2026-04-05T00:00:00Z",
              is_latest: true,
            },
          ],
        },
      ],
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请帮我梳理目标用户。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "先把问题范围说清楚。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
    });
    const postRegenerateSnapshot = createSessionSnapshot({
      assistant_reply_groups: [
        {
          id: "group-1",
          session_id: "demo-session",
          user_message_id: "user-1",
          latest_version_id: "version-2",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
          versions: [
            {
              id: "version-1",
              reply_group_id: "group-1",
              session_id: "demo-session",
              user_message_id: "user-1",
              version_no: 1,
              content: "先把问题范围说清楚。",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 2,
              created_at: "2026-04-05T00:00:00Z",
              is_latest: false,
            },
            {
              id: "version-2",
              reply_group_id: "group-1",
              session_id: "demo-session",
              user_message_id: "user-1",
              version_no: 2,
              content: "重新生成后的回复。",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 3,
              created_at: "2026-04-05T00:00:00Z",
              is_latest: true,
            },
          ],
        },
      ],
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请帮我梳理目标用户。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-2",
          session_id: "demo-session",
          role: "assistant",
          content: "重新生成后的回复。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 2,
          is_latest: true,
        },
      ],
    });
    vi.mocked(getSession)
      .mockResolvedValueOnce(postSendSnapshot)
      .mockResolvedValueOnce(postRegenerateSnapshot);

    render(<ConversationPanel sessionId="demo-session" />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "请帮我梳理目标用户。" },
    });

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => {
      expect(workspaceStore.getState().lastSubmittedInput).toBe("请帮我梳理目标用户。");
    });

    const regenerateButton = await screen.findByRole("button", { name: "重新生成" });
    expect(regenerateButton).not.toBeDisabled();
    fireEvent.click(regenerateButton);

    expect(screen.getByRole("button", { name: "生成中..." })).toBeDisabled();

    await waitFor(() => {
      expect(vi.mocked(sendMessage)).toHaveBeenCalledTimes(1);
      expect(vi.mocked(regenerateMessage)).toHaveBeenCalledTimes(1);
    });

    expect(vi.mocked(sendMessage)).toHaveBeenNthCalledWith(
      1,
      "demo-session",
      "请帮我梳理目标用户。",
      null,
      expect.any(AbortSignal),
      "model-openai",
    );
    expect(vi.mocked(regenerateMessage)).toHaveBeenNthCalledWith(
      1,
      "demo-session",
      "user-1",
      null,
      expect.any(AbortSignal),
      "model-openai",
    );
    expect(
      workspaceStore.getState().messages.filter((message) => message.role === "user"),
    ).toHaveLength(1);
    expect(workspaceStore.getState().messages.at(-1)?.content).toContain("重新生成后的回复");
    await waitFor(() => {
      expect(vi.mocked(getSession)).toHaveBeenCalledTimes(2);
    });
    expect(workspaceStore.getState().messages).toEqual(
      normalizeMessagesForTest(postRegenerateSnapshot.messages),
    );
  });

  it("keeps single-input send flow after completion and relies on refreshed snapshot to reopen", async () => {
    workspaceStore.getState().hydrateSession(createSessionSnapshot({
      state: {
        workflow_stage: "completed",
        finalization_ready: true,
        prd_draft: {
          version: 4,
          status: "finalized",
        },
      },
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请整理最终版本。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "这是最终整理后的 PRD 版本。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
    }));
    workspaceStore.getState().setInputValue("我想补充一个约束条件。");

    const encoder = new TextEncoder();
    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode('event: message.accepted\ndata: {"message_id":"user-2"}\n\n'),
          );
          controller.close();
        },
      }),
    );
    vi.mocked(getSession).mockResolvedValueOnce(createSessionSnapshot({
      state: {
        workflow_stage: "refine_loop",
        finalization_ready: false,
        prd_draft: {
          version: 5,
          status: "draft",
        },
      },
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请整理最终版本。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "这是最终整理后的 PRD 版本。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
        {
          id: "user-2",
          session_id: "demo-session",
          role: "user",
          content: "我想补充一个约束条件。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
      ],
    }));

    render(<Composer sessionId="demo-session" />);
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => {
      expect(sendMessage).toHaveBeenCalledWith(
        "demo-session",
        "我想补充一个约束条件。",
        null,
        expect.any(AbortSignal),
        "model-openai",
      );
    });
    await waitFor(() => {
      expect(workspaceStore.getState().workflowStage).toBe("refine_loop");
      expect(workspaceStore.getState().isCompleted).toBe(false);
    });
  });

  it("guards regenerate against rapid duplicate triggers", async () => {
    vi.mocked(regenerateMessage).mockImplementation(
      () =>
        new Promise<ReadableStream<Uint8Array>>(() => {
          // keep pending to expose duplicate trigger bugs
        }),
    );

    workspaceStore.getState().hydrateSession(createSessionSnapshot({
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请帮我梳理目标用户。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "先把问题范围说清楚。",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
      assistant_reply_groups: [
        {
          id: "group-1",
          session_id: "demo-session",
          user_message_id: "user-1",
          latest_version_id: "version-1",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
          versions: [
            {
              id: "version-1",
              reply_group_id: "group-1",
              session_id: "demo-session",
              user_message_id: "user-1",
              version_no: 1,
              content: "先把问题范围说清楚。",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 2,
              created_at: "2026-04-05T00:00:00Z",
              is_latest: true,
            },
          ],
        },
      ],
    }));

    render(<ConversationPanel sessionId="demo-session" />);

    const regenerateButton = screen.getByRole("button", { name: "重新生成" });
    fireEvent.click(regenerateButton);
    fireEvent.click(regenerateButton);

    await waitFor(() => {
      expect(regenerateMessage).toHaveBeenCalledTimes(1);
    });
  });

  it("hides regenerate when no selected model is available", () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      availableModelConfigs: [],
      selectedModelConfigId: null,
      lastSubmittedInput: "请帮我梳理目标用户。",
      currentAction: null,
      messages: [
        {
          id: "assistant-1",
          role: "assistant",
          content: "先把问题范围说清楚。",
        },
      ],
    });

    render(<ConversationPanel sessionId="demo-session" />);

    expect(screen.queryByRole("button", { name: "重新生成" })).not.toBeInTheDocument();
    expect(vi.mocked(sendMessage)).not.toHaveBeenCalled();
    expect(workspaceStore.getState().isStreaming).toBe(false);
    expect(workspaceStore.getState().streamPhase).toBe("idle");
    expect(workspaceStore.getState().pendingRequestMode).toBeNull();
  });

  it("aborts regenerateMessage when stopping an in-flight regenerate request", async () => {
    const encoder = new TextEncoder();
    let capturedSignal: AbortSignal | undefined;
    const postSendSnapshot = createSessionSnapshot({
      assistant_reply_groups: [
        {
          id: "group-1",
          session_id: "demo-session",
          user_message_id: "user-1",
          latest_version_id: "version-1",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
          versions: [
            {
              id: "version-1",
              reply_group_id: "group-1",
              session_id: "demo-session",
              user_message_id: "user-1",
              version_no: 1,
              content: "初版回复",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 2,
              created_at: "2026-04-05T00:00:00Z",
              is_latest: true,
            },
          ],
        },
      ],
      messages: [
        {
          id: "user-1",
          session_id: "demo-session",
          role: "user",
          content: "请帮我梳理目标用户。",
          message_type: "text",
          reply_group_id: null,
          version_no: null,
          is_latest: true,
        },
        {
          id: "assistant-1",
          session_id: "demo-session",
          role: "assistant",
          content: "初版回复",
          message_type: "text",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
    });

    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: message.accepted\ndata: {"message_id":"user-1","session_id":"demo-session"}\n\n' +
                'event: reply_group.created\ndata: {"reply_group_id":"group-1","user_message_id":"user-1","session_id":"demo-session","is_regeneration":false,"is_latest":false}\n\n' +
                'event: assistant.version.started\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-1","version_no":1,"assistant_message_id":null,"model_config_id":"model-openai","is_regeneration":false,"is_latest":false}\n\n' +
                'event: assistant.delta\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-1","version_no":1,"assistant_message_id":null,"model_config_id":"model-openai","delta":"初版回复","is_regeneration":false,"is_latest":false}\n\n' +
                'event: assistant.done\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-1","version_id":"version-1","version_no":1,"assistant_message_id":"assistant-1","model_config_id":"model-openai","prd_snapshot_version":2,"is_regeneration":false,"is_latest":true}\n\n',
            ),
          );
          controller.close();
        },
      }),
    );
    vi.mocked(getSession).mockResolvedValueOnce(postSendSnapshot);
    vi.mocked(regenerateMessage).mockImplementation(async (_sessionId, _userMessageId, _token, signal) => {
      capturedSignal = signal;
      return new Promise<ReadableStream<Uint8Array>>((_, reject) => {
        signal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        });
      });
    });

    render(<ConversationPanel sessionId="demo-session" />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "请帮我梳理目标用户。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    const regenerateButton = await screen.findByRole("button", { name: "重新生成" });
    expect(regenerateButton).not.toBeDisabled();

    fireEvent.click(regenerateButton);
    fireEvent.click(await screen.findByRole("button", { name: "停止生成" }));

    await waitFor(() => {
      expect(workspaceStore.getState().isStreaming).toBe(false);
    });

    expect(capturedSignal?.aborted).toBe(true);
    expect(vi.mocked(regenerateMessage)).toHaveBeenCalledWith(
      "demo-session",
      "user-1",
      null,
      expect.any(AbortSignal),
      "model-openai",
    );
  });

  it("derives regenerate user_message_id from the latest assistant reply group after hydrate", async () => {
    vi.mocked(regenerateMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.close();
        },
      }),
    );

    workspaceStore.setState({
      ...workspaceStore.getState(),
      currentAction: null,
      messages: [
        {
          id: "user-1",
          role: "user",
          content: "请帮我梳理目标用户。",
        },
        {
          id: "version-1",
          role: "assistant",
          content: "先把问题范围说清楚。",
          replyGroupId: "group-1",
          versionNo: 1,
          isLatest: true,
        },
      ],
      replyGroups: {
        "group-1": {
          id: "group-1",
          sessionId: "demo-session",
          userMessageId: "user-1",
          latestVersionId: "version-1",
          versions: [
            {
              id: "version-1",
              versionNo: 1,
              content: "先把问题范围说清楚。",
              assistantMessageId: "assistant-1",
              isRegeneration: false,
              isLatest: true,
            },
          ],
        },
      },
      lastSubmittedInput: null,
    });

    render(<ConversationPanel sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "重新生成" }));

    await waitFor(() => {
      expect(vi.mocked(regenerateMessage)).toHaveBeenCalledWith(
        "demo-session",
        "user-1",
        null,
        expect.any(AbortSignal),
        "model-openai",
      );
    });
  });

  it("offers an immediate regenerate after switching to the recommended model", async () => {
    const encoder = new TextEncoder();
    workspaceStore.getState().setAvailableModelConfigs([
      {
        id: "model-openai",
        name: "OpenAI GPT-4.1",
        model: "gpt-4.1",
      },
      {
        id: "model-anthropic",
        name: "Anthropic Claude 3.7",
        model: "claude-3-7-sonnet",
      },
    ]);

    vi.mocked(regenerateMessage)
      .mockRejectedValueOnce(
        Object.assign(new Error("当前模型不可用，请选择其他模型后重试"), {
          code: "MODEL_CONFIG_DISABLED",
          details: {
            recommended_model_config_id: "model-anthropic",
            recommended_model_scene: "reasoning",
            recommended_model_name: "Anthropic Claude 3.7",
            recommended_model_reason: "它更适合继续长文本推理，建议优先切到这个模型继续。",
            requested_model_config_id: "model-openai",
          },
          recoveryAction: {
            type: "select_available_model",
            label: "选择可用模型",
            target: null,
          },
        }),
      )
      .mockResolvedValueOnce(
        new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(
              encoder.encode('event: assistant.version.started\ndata: {"session_id":"demo-session","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-2","version_no":2,"assistant_message_id":"assistant-1","model_config_id":"model-anthropic","is_regeneration":true,"is_latest":false}\n\n'),
            );
            controller.close();
          },
        }),
      );

    workspaceStore.setState({
      ...workspaceStore.getState(),
      lastSubmittedInput: "请帮我梳理目标用户。",
      pendingRequestMode: "regenerate",
      pendingUserInput: "请帮我梳理目标用户。",
      regenerateRequestId: 1,
    });

    render(<Composer sessionId="demo-session" regenerateUserMessageId="user-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "切换到 Anthropic Claude 3.7" }));
    expect(
      await screen.findByText(
        "已切换到 Anthropic Claude 3.7。按当前对话场景优先推荐：长文本推理。它更适合继续长文本推理，建议优先切到这个模型继续。",
      ),
    ).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "立即重新生成" }));

    await waitFor(() => {
      expect(regenerateMessage).toHaveBeenNthCalledWith(
        2,
        "demo-session",
        "user-1",
        null,
        expect.any(AbortSignal),
        "model-anthropic",
      );
    });
  });
});

describe("ConversationPanel decision guidance", () => {
  const openaiConfig = {
    id: "model-openai",
    name: "OpenAI GPT-4.1",
    model: "gpt-4.1",
  };
  const guidanceQuestions = [
    "确认当前目标用户是哪个人群？",
    "确认下一步验证的关键假设。",
  ];

  beforeEach(() => {
    workspaceStore.setState(workspaceStore.getInitialState(), true);
    workspaceStore.getState().setAvailableModelConfigs([openaiConfig]);
  });

  it("shows the latest guidance and populates the input when a recommendation is clicked", async () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "choose",
      strategyLabel: "取舍中",
      strategyReason: "需要先确定空之间的优先级",
      nextBestQuestions: [
        ...guidanceQuestions,
      ],
      confirmQuickReplies: [],
    };

    workspaceStore.setState({
      messages: [
        { id: "user-1", role: "user", content: "先讲清问题" },
        { id: "assistant-1", role: "assistant", content: "我们先判断取舍" },
      ],
      decisionGuidance: guidance,
    });
    workspaceStore.getState().setInputValue("已有草稿");

    render(<ConversationPanel sessionId="session-1" />);

    guidance.nextBestQuestions.forEach((question) => {
      const button = screen.getByRole("button", { name: question });
      expect(button).toBeInTheDocument();
    });

    const firstQuestion = guidance.nextBestQuestions[0];
    fireEvent.click(screen.getByRole("button", { name: firstQuestion }));
    await waitFor(() => {
      expect(workspaceStore.getState().inputValue).toBe(firstQuestion);
      expect(screen.getByRole("textbox")).toHaveValue(firstQuestion);
    });
  });

  it("keeps existing history and controls when no guidance is available", () => {
    workspaceStore.setState({
      messages: [
        { id: "user-1", role: "user", content: "先讲清问题" },
        { id: "assistant-1", role: "assistant", content: "我们先判断取舍" },
      ],
      decisionGuidance: null,
    });

    render(<ConversationPanel sessionId="session-1" />);

    guidanceQuestions.forEach((question) => {
      expect(screen.queryByRole("button", { name: question })).not.toBeInTheDocument();
    });
    expect(screen.getByText("先讲清问题")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送消息" })).toBeInTheDocument();
  });

  it("hides decision guidance while streaming", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "choose",
      strategyLabel: "取舍中",
      strategyReason: "需要先确定空之间的优先级",
      nextBestQuestions: guidanceQuestions,
      confirmQuickReplies: [],
    };

    workspaceStore.setState({
      ...workspaceStore.getState(),
      messages: [
        { id: "user-1", role: "user", content: "先讲清问题" },
        { id: "assistant-1", role: "assistant", content: "我们先判断取舍" },
      ],
      decisionGuidance: guidance,
      isStreaming: true,
      streamPhase: "streaming",
    });

    render(<ConversationPanel sessionId="session-1" />);

    guidanceQuestions.forEach((question) => {
      expect(screen.queryByRole("button", { name: question })).not.toBeInTheDocument();
    });
    expect(screen.queryByText("下一步建议")).not.toBeInTheDocument();
  });

  it("hides decision guidance while waiting", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "choose",
      strategyLabel: "取舍中",
      strategyReason: "需要先确定空之间的优先级",
      nextBestQuestions: guidanceQuestions,
      confirmQuickReplies: [],
    };

    workspaceStore.setState({
      ...workspaceStore.getState(),
      messages: [
        { id: "user-1", role: "user", content: "先讲清问题" },
        { id: "assistant-1", role: "assistant", content: "我们先判断取舍" },
      ],
      decisionGuidance: guidance,
      streamPhase: "waiting",
      pendingRequestMode: "new",
    });

    render(<ConversationPanel sessionId="session-1" />);

    guidanceQuestions.forEach((question) => {
      expect(screen.queryByRole("button", { name: question })).not.toBeInTheDocument();
    });
    expect(screen.queryByText("下一步建议")).not.toBeInTheDocument();
  });

  it("fills the composer input when a structured suggestion option is clicked", async () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "greet",
      strategyLabel: "欢迎引导",
      strategyReason: "先给用户几个容易选择的方向。",
      nextBestQuestions: [],
      confirmQuickReplies: [],
      suggestionOptions: [
        {
          label: "从模糊方向开始",
          content: "我现在只有一个模糊方向，还不知道怎么描述，想让你带着我一步步梳理。",
          rationale: "适合还在很早期、需要 AI 先给框架的情况。",
          priority: 1,
          type: "direction",
        },
      ],
    };

    workspaceStore.setState({
      messages: [
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "先选一个最接近你的方向。" },
      ],
      decisionGuidance: guidance,
    });

    render(<ConversationPanel sessionId="session-1" />);

    fireEvent.click(screen.getByRole("button", { name: /从模糊方向开始/i }));

    await waitFor(() => {
      expect(workspaceStore.getState().inputValue).toBe("我现在只有一个模糊方向，还不知道怎么描述，想让你带着我一步步梳理。");
      expect(screen.getByRole("textbox")).toHaveValue("我现在只有一个模糊方向，还不知道怎么描述，想让你带着我一步步梳理。");
    });
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("focuses the composer for free supplement without overwriting the current draft or sending", async () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "greet",
      strategyLabel: "欢迎引导",
      strategyReason: "先给用户几个容易选择的方向。",
      nextBestQuestions: [],
      confirmQuickReplies: [],
      suggestionOptions: [
        {
          label: "先聊目标用户",
          content: "我想先把目标用户讲清楚，再继续往下拆。",
          rationale: "先定用户，后续问题和方案更容易收敛。",
          priority: 1,
          type: "direction",
        },
        {
          label: "先聊使用场景",
          content: "我想先把用户会在哪个场景下使用这款产品讲清楚。",
          rationale: "先锁定场景，便于判断需求强度。",
          priority: 2,
          type: "direction",
        },
        {
          label: "先聊核心痛点",
          content: "我想先确认用户最痛的那个问题到底是什么。",
          rationale: "先抓痛点，再看功能是否成立。",
          priority: 3,
          type: "direction",
        },
        {
          label: "先聊验证方式",
          content: "我想先聊第一轮要怎么验证这个想法值不值得做。",
          rationale: "优先明确验证动作，降低空想风险。",
          priority: 4,
          type: "direction",
        },
      ],
      freeformAffordance: {
        label: "都不对，我补充",
        value: "freeform",
        kind: "freeform",
      },
    };

    workspaceStore.setState({
      messages: [
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "先选一个最接近你的方向。" },
      ],
      decisionGuidance: guidance,
    });
    workspaceStore.getState().setInputValue("已有草稿");

    render(<ConversationPanel sessionId="session-1" />);

    fireEvent.click(screen.getByRole("button", { name: /都不对，我补充/i }));

    await waitFor(() => {
      expect(screen.getByRole("textbox")).toHaveFocus();
    });
    expect(workspaceStore.getState().inputValue).toBe("已有草稿");
    expect(screen.getByRole("textbox")).toHaveValue("已有草稿");
    expect(sendMessage).not.toHaveBeenCalled();
  });
});
