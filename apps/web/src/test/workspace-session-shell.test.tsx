import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceSessionShell } from "../components/workspace/workspace-session-shell";


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
    getSessionMock.mockResolvedValue({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
      },
      state: {
        idea: "idea",
        stage_hint: "理解问题",
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
});
