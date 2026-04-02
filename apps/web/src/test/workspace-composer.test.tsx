import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Composer } from "../components/workspace/composer";
import { sendMessage } from "../lib/api";
import { workspaceStore } from "../store/workspace-store";


vi.mock("../lib/api", () => ({
  sendMessage: vi.fn(),
}));


describe("Composer", () => {
  beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
  });

  it("releases the streaming lock when the sse stream ends without assistant.done", async () => {
    const encoder = new TextEncoder();
    vi.mocked(sendMessage).mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: message.accepted\ndata: {"message_id":"user-1"}\n\n' +
                'event: assistant.delta\ndata: {"delta":"继续收窄目标用户。"}\n\n',
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
});
