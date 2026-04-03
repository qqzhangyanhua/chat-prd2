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
    workspaceStore.getState().setInputValue("请继续追问目标用户");
  });

  it("releases the streaming lock when the sse stream ends without assistant.done", async () => {
    const encoder = new TextEncoder();
    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: message.accepted\ndata: {"message_id":"user-1"}\n\n' +
                'event: assistant.delta\ndata: {"delta":"先确认目标用户。"}\n\n',
            ),
          );
          controller.close();
        },
      }),
    );

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "继续推进" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "继续推进" })).not.toBeDisabled();
    });
  });

  it("shows a global toast when sending a message fails", async () => {
    vi.mocked(sendMessage).mockRejectedValue(new Error("消息发送失败"));

    render(<Composer sessionId="demo-session" />);

    fireEvent.click(screen.getByRole("button", { name: "继续推进" }));

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("消息发送失败");
    });
    expect(await screen.findByText("消息发送失败")).toBeInTheDocument();
  });
});
