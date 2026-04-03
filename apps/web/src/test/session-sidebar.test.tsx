import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionSidebar } from "../components/workspace/session-sidebar";


const exportSessionMock = vi.fn();
const getSessionMock = vi.fn();

vi.mock("../lib/api", () => ({
  exportSession: (...args: unknown[]) => exportSessionMock(...args),
  getSession: (...args: unknown[]) => getSessionMock(...args),
}));


describe("SessionSidebar", () => {
  beforeEach(() => {
    exportSessionMock.mockReset();
    getSessionMock.mockReset();
  });

  it("calls export when clicking export prd", async () => {
    exportSessionMock.mockResolvedValue({
      file_name: "ai-cofounder-prd.md",
      content: "# PRD",
    });

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.click(screen.getByRole("button", { name: "导出 PRD" }));

    await waitFor(() => {
      expect(exportSessionMock).toHaveBeenCalledWith("session-1", null);
    });
  });

  it("requests current session when clicking recover session", async () => {
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

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.click(screen.getByRole("button", { name: "恢复会话" }));

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledWith("session-1", null);
    });
  });
});
