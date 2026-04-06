import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationPanel } from "../components/workspace/conversation-panel";
import { Composer } from "../components/workspace/composer";
import { regenerateMessage } from "../lib/api";
import { sendMessage } from "../lib/api";
import { useToastStore } from "../store/toast-store";
import { workspaceStore } from "../store/workspace-store";

vi.mock("../lib/api", () => ({
  sendMessage: vi.fn(),
  regenerateMessage: vi.fn(),
}));

describe("Composer", () => {
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
});

describe("ConversationPanel empty state", () => {
  beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    vi.mocked(regenerateMessage).mockReset();
    useToastStore.getState().clearToast();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
  });

  it("shows empty state when no messages and not streaming", () => {
    render(<ConversationPanel sessionId="session-1" />);

    expect(screen.getByText(/开始描述你的想法/i)).toBeInTheDocument();
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

    render(<ConversationPanel sessionId="demo-session" />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "请帮我梳理目标用户。" },
    });

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await waitFor(() => {
      expect(workspaceStore.getState().lastSubmittedInput).toBe("请帮我梳理目标用户。");
    });

    expect(screen.getByRole("button", { name: "重新生成" })).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "重新生成" }));

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

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "重新生成" })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "重新生成" }));
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
});
