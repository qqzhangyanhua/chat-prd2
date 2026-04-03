import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionSidebar } from "../components/workspace/session-sidebar";

const exportSessionMock = vi.fn();
const getSessionMock = vi.fn();
const listSessionsMock = vi.fn();
const deleteSessionMock = vi.fn();
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
  deleteSession: (...args: unknown[]) => deleteSessionMock(...args),
  updateSession: (...args: unknown[]) => updateSessionMock(...args),
}));

describe("SessionSidebar", () => {
  beforeEach(() => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-04-03T12:45:00Z").getTime());
    vi.spyOn(window, "confirm").mockReturnValue(true);

    exportSessionMock.mockReset();
    getSessionMock.mockReset();
    listSessionsMock.mockReset();
    deleteSessionMock.mockReset();
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

  afterEach(() => {
    vi.restoreAllMocks();
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
        stage_hint: "澄清问题",
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

  it("shows recent activity as relative time", async () => {
    render(<SessionSidebar sessionId="session-1" />);

    expect((await screen.findAllByText("最近活跃 15 分钟前")).length).toBeGreaterThan(0);
    expect(screen.getByText("最近活跃 1 小时前")).toBeInTheDocument();
  });

  it("does not submit rename when title is empty after trimming", async () => {
    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.change(await screen.findByLabelText("会话标题"), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存标题" }));

    await waitFor(() => {
      expect(updateSessionMock).not.toHaveBeenCalled();
    });
    expect(screen.getByText("会话标题不能为空")).toBeInTheDocument();
  });

  it("shows rename error when update request fails", async () => {
    updateSessionMock.mockRejectedValue(new Error("重命名失败"));

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.change(await screen.findByLabelText("会话标题"), {
      target: { value: "新标题" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存标题" }));

    expect(await screen.findByText("重命名失败")).toBeInTheDocument();
  });

  it("does not delete the session when confirmation is cancelled", async () => {
    vi.mocked(window.confirm).mockReturnValue(false);

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "删除会话" }));

    expect(deleteSessionMock).not.toHaveBeenCalled();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("deletes the active session after confirmation and returns to workspace entry", async () => {
    deleteSessionMock.mockResolvedValue(undefined);

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "删除会话" }));

    expect(window.confirm).toHaveBeenCalledWith("确认删除当前会话？此操作不可恢复。");
    await waitFor(() => {
      expect(deleteSessionMock).toHaveBeenCalledWith("session-1", null);
    });
    expect(pushMock).toHaveBeenCalledWith("/workspace");
  });

  it("shows delete error when request fails", async () => {
    deleteSessionMock.mockRejectedValue(new Error("删除失败"));

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "删除会话" }));

    expect(await screen.findByText("删除失败")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("disables delete button and shows loading while deleting", async () => {
    let resolveDelete: (() => void) | null = null;
    deleteSessionMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        }),
    );

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "删除会话" }));

    const deletingButton = await screen.findByRole("button", { name: "删除中..." });
    expect(deletingButton).toBeDisabled();
    expect(deleteSessionMock).toHaveBeenCalledTimes(1);

    fireEvent.click(deletingButton);
    expect(deleteSessionMock).toHaveBeenCalledTimes(1);

    resolveDelete?.();
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/workspace");
    });
  });
});
