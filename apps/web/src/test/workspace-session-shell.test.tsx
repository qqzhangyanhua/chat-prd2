import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
      },
      state: {
        idea: "idea",
        stage_hint: "明确问题",
      },
      prd_snapshot: {
        sections: {},
      },
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
    expect(await screen.findByText("会话加载失败")).toBeInTheDocument();
  });
});
