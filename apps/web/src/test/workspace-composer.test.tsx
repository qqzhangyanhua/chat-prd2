import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationPanel } from "../components/workspace/conversation-panel";
import { Composer } from "../components/workspace/composer";
import { sendMessage } from "../lib/api";
import { useToastStore } from "../store/toast-store";
import { workspaceStore } from "../store/workspace-store";

vi.mock("../lib/api", () => ({
  sendMessage: vi.fn(),
}));

describe("Composer", () => {
  beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    useToastStore.getState().clearToast();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
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
      expect(screen.getByRole("button", { name: "发送消息" })).not.toBeDisabled();
    });
  });

  it("shows waiting and generating statuses while sending", async () => {
    const encoder = new TextEncoder();
    let controllerRef: ReadableStreamDefaultController<Uint8Array> | null = null;

    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controllerRef = controller;
          controller.enqueue(
            encoder.encode('event: message.accepted\ndata: {"message_id":"user-1"}\n\n'),
          );
        },
      }),
    );

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(await screen.findByText("等待回应...")).toBeInTheDocument();

    controllerRef?.enqueue(
      encoder.encode('event: assistant.delta\ndata: {"delta":"继续展开这个想法。"}\n\n'),
    );
    controllerRef?.close();

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
      expect(screen.getByRole("button", { name: "发送消息" })).not.toBeDisabled();
    });

    expect(capturedSignal?.aborted).toBe(true);
    expect(screen.getByText("准备好继续，补充你的想法。")).toBeInTheDocument();
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
      expect(screen.getByRole("button", { name: "发送消息" })).not.toBeDisabled();
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
});

describe("ConversationPanel regenerate", () => {
  beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    useToastStore.getState().clearToast();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
  });

  it("replays the latest accepted input without adding a duplicate user message", async () => {
    const encoder = new TextEncoder();
    let callCount = 0;

    vi.mocked(sendMessage).mockImplementation(async () => {
      callCount += 1;
      if (callCount === 1) {
        return new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                'event: message.accepted\ndata: {"message_id":"user-1"}\n\n' +
                  'event: assistant.delta\ndata: {"delta":"先把问题范围说清楚。"}\n\n',
              ),
            );
            controller.close();
          },
        });
      }

      return new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: message.accepted\ndata: {"message_id":"user-2"}\n\n' +
                'event: assistant.delta\ndata: {"delta":"重新生成后的回复。"}\n\n',
            ),
          );
          controller.close();
        },
      });
    });

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

    expect(screen.getByRole("button", { name: "重新生成中..." })).toBeDisabled();

    await waitFor(() => {
      expect(vi.mocked(sendMessage)).toHaveBeenCalledTimes(2);
    });

    expect(
      workspaceStore.getState().messages.filter((message) => message.role === "user"),
    ).toHaveLength(1);
    expect(workspaceStore.getState().messages.at(-1)?.content).toContain("重新生成后的回复");
  });
});
