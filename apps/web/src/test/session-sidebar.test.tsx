import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionSidebar } from "../components/workspace/session-sidebar";


const exportSessionMock = vi.fn();
const getSessionMock = vi.fn();
const listSessionsMock = vi.fn();
const updateSessionMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", () => ({
  exportSession: (...args: unknown[]) => exportSessionMock(...args),
  getSession: (...args: unknown[]) => getSessionMock(...args),
  listSessions: (...args: unknown[]) => listSessionsMock(...args),
  updateSession: (...args: unknown[]) => updateSessionMock(...args),
}));


describe("SessionSidebar", () => {
  beforeEach(() => {
    exportSessionMock.mockReset();
    getSessionMock.mockReset();
    listSessionsMock.mockReset();
    updateSessionMock.mockReset();
    pushMock.mockReset();
    listSessionsMock.mockResolvedValue({
      sessions: [
        {
          id: "session-1",
          user_id: "user-1",
          title: "当前项目",
          initial_idea: "idea",
          created_at: "2026-04-03T12:00:00Z",
          updated_at: "2026-04-03T12:30:00Z",
        },
        {
          id: "session-2",
          user_id: "user-1",
          title: "另一个项目",
          initial_idea: "another idea",
          created_at: "2026-04-03T10:00:00Z",
          updated_at: "2026-04-03T11:00:00Z",
        },
      ],
    });
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

  it("loads sessions and switches to the selected session", async () => {
    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.click(await screen.findByText("另一个项目"));

    expect(listSessionsMock).toHaveBeenCalledWith(null);
    expect(pushMock).toHaveBeenCalledWith("/workspace/session-2");
  });

  it("renames the active session", async () => {
    updateSessionMock.mockResolvedValue({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "改过的标题",
        initial_idea: "idea",
        created_at: "2026-04-03T12:00:00Z",
        updated_at: "2026-04-03T12:40:00Z",
      },
    });

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.change(await screen.findByLabelText("会话标题"), {
      target: { value: "改过的标题" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存标题" }));

    await waitFor(() => {
      expect(updateSessionMock).toHaveBeenCalledWith("session-1", { title: "改过的标题" }, null);
    });
  });

  it("shows recent activity timestamps", async () => {
    render(<SessionSidebar sessionId="session-1" />);

    expect(await screen.findByText(/最近活跃/)).toBeInTheDocument();
  });
});
