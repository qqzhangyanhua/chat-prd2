import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
    workspaceStore.getState().setInputValue("我想先服务独立开发者，让他们更快梳理产品方向。");
  });

  it("releases the streaming lock when the sse stream ends without assistant.done", async () => {
    const encoder = new TextEncoder();
    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: message.accepted\ndata: {"message_id":"user-1"}\n\n' +
                'event: assistant.delta\ndata: {"delta":"先把目标用户再缩窄一层。"}\n\n',
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

    expect(await screen.findByText("正在等待智能体回应...")).toBeInTheDocument();

    controllerRef?.enqueue(
      encoder.encode('event: assistant.delta\ndata: {"delta":"先讲讲你最想解决的真实场景。"}\n\n'),
    );
    controllerRef?.close();

    expect(await screen.findByText("正在生成回复...")).toBeInTheDocument();
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
