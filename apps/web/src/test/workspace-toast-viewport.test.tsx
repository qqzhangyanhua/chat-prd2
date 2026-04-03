import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceToastViewport } from "../components/workspace/workspace-toast-viewport";
import { useToastStore } from "../store/toast-store";

describe("WorkspaceToastViewport", () => {
  beforeEach(() => {
    useToastStore.getState().clearToast();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("auto clears info toasts", async () => {
    useToastStore.getState().showToast({
      message: "已停止本轮生成",
      tone: "info",
    });

    render(<WorkspaceToastViewport />);

    expect(screen.getByRole("status")).toHaveTextContent("已停止本轮生成");

    await act(async () => {
      vi.advanceTimersByTime(2500);
    });

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
