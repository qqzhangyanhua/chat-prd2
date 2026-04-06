import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getSession } from "../lib/api";

import { WorkspaceSessionShell } from "../components/workspace/workspace-session-shell";
import { useToastStore } from "../store/toast-store";

const getSessionMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", () => ({
  getSession: (...args: unknown[]) => getSessionMock(...args),
}));

describe("WorkspaceSessionShell", () => {
  beforeEach(() => {
    getSessionMock.mockReset();
    pushMock.mockReset();
    useToastStore.getState().clearToast();
    getSessionMock.mockResolvedValue({
      session: {
        id: "session-1",
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
    });
  });

  it("loads the current session snapshot on mount", async () => {
    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledWith("session-1", null);
    });
  });

  it("shows a global toast when session loading fails", async () => {
    getSessionMock.mockRejectedValue(new Error("会话加载失败"));

    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("会话加载失败");
    });

    const toast = await screen.findByRole("status");
    expect(toast).toHaveTextContent("会话加载失败");
    expect(await screen.findByRole("button", { name: "重试加载" })).toBeInTheDocument();
  });

  it("shows loading skeleton while session is loading", () => {
    getSessionMock.mockImplementation(
      () => new Promise(() => {}), // never resolves — keeps loading state
    );

    render(<WorkspaceSessionShell sessionId="session-1" />);

    expect(screen.getByTestId("session-loading-skeleton")).toBeInTheDocument();
  });

  it("hides skeleton after session loads", async () => {
    getSessionMock.mockResolvedValue({
      session: {
        id: "session-1",
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
    });

    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(screen.queryByTestId("session-loading-skeleton")).not.toBeInTheDocument();
    });
  });

  it("renders a retry action after session loading fails", async () => {
    getSessionMock
      .mockRejectedValueOnce(new Error("会话加载失败"))
      .mockResolvedValueOnce({
        session: {
          id: "session-1",
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
      });

    render(<WorkspaceSessionShell sessionId="session-1" />);

    const retryButton = await screen.findByRole("button", { name: "重试加载" });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledTimes(2);
    });
  });
});
