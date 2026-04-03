import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionSidebar } from "../components/workspace/session-sidebar";
import { useToastStore } from "../store/toast-store";

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
    useToastStore.getState().clearToast();

    listSessionsMock.mockResolvedValue({
      sessions: [
        {
          id: "session-1",
          user_id: "user-1",
          title: "产品调研",
          initial_idea: "idea",
          created_at: "2026-04-03T12:00:00Z",
          updated_at: "2026-04-03T12:30:00Z",
        },
        {
          id: "session-2",
          user_id: "user-1",
          title: "定价策略",
          initial_idea: "another idea",
          created_at: "2026-04-03T10:00:00Z",
          updated_at: "2026-04-03T11:00:00Z",
        },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    useToastStore.getState().clearToast();
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
        stage_hint: "明确目标用户",
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

    fireEvent.click(await screen.findByRole("button", { name: "打开会话 定价策略" }));

    expect(listSessionsMock).toHaveBeenCalledWith(null);
    expect(pushMock).toHaveBeenCalledWith("/workspace/session-2");
  });

  it("renames the active session", async () => {
    updateSessionMock.mockResolvedValue({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "竞品分析",
        initial_idea: "idea",
        created_at: "2026-04-03T12:00:00Z",
        updated_at: "2026-04-03T12:40:00Z",
      },
    });

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.change(await screen.findByLabelText("会话标题"), {
      target: { value: "竞品分析" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存标题" }));

    await waitFor(() => {
      expect(updateSessionMock).toHaveBeenCalledWith(
        "session-1",
        { title: "竞品分析" },
        null,
      );
    });
  });

  it("shows recent activity as relative time", async () => {
    render(<SessionSidebar sessionId="session-1" />);

    expect((await screen.findAllByText("15 分钟前")).length).toBeGreaterThan(0);
    expect(screen.getByText("1 小时前")).toBeInTheDocument();
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
      target: { value: "访谈提纲" },
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

  it("shows deleting toast and disables the active session card while deleting", async () => {
    let resolveDelete: (() => void) | null = null;
    deleteSessionMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        }),
    );

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "删除会话" }));

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("正在删除会话...");
    });

    expect(screen.getByRole("button", { name: "打开会话 产品调研" })).toBeDisabled();

    resolveDelete?.();
    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("会话已删除");
    });
  });

  it("shows rename success toast and disables rename button while saving", async () => {
    let resolveRename: ((value: { session: { id: string; user_id: string; title: string; initial_idea: string; created_at: string; updated_at: string } }) => void) | null = null;
    updateSessionMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRename = resolve;
        }),
    );

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.change(await screen.findByLabelText("会话标题"), {
      target: { value: "访谈提纲" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存标题" }));

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("正在保存标题...");
    });
    expect(screen.getByRole("button", { name: "保存中..." })).toBeDisabled();

    resolveRename?.({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "访谈提纲",
        initial_idea: "idea",
        created_at: "2026-04-03T12:00:00Z",
        updated_at: "2026-04-03T12:40:00Z",
      },
    });

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("标题已更新");
    });
  });

  it("shows rename failure toast when update request fails", async () => {
    updateSessionMock.mockRejectedValue(new Error("重命名失败"));

    render(<SessionSidebar sessionId="session-1" />);

    fireEvent.change(await screen.findByLabelText("会话标题"), {
      target: { value: "访谈提纲" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存标题" }));

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("重命名失败");
    });
  });

  it("shows recover toast and disables recover button while recovering", async () => {
    let resolveRecover: ((value: {
      session: { id: string; user_id: string; title: string; initial_idea: string };
      state: { idea: string; stage_hint: string };
      prd_snapshot: { sections: Record<string, never> };
    }) => void) | null = null;
    getSessionMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRecover = resolve;
        }),
    );

    render(<SessionSidebar sessionId="session-1" />);

    await screen.findByRole("button", { name: "打开会话 产品调研" });

    fireEvent.click(screen.getByRole("button", { name: "恢复会话" }));

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("正在恢复会话...");
    });
    expect(screen.getByRole("button", { name: "恢复中..." })).toBeDisabled();

    resolveRecover?.({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
      },
      state: {
        idea: "idea",
        stage_hint: "明确目标用户",
      },
      prd_snapshot: {
        sections: {},
      },
    });

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("会话已恢复");
    });
  });

  it("shows export toast and disables export button while exporting", async () => {
    let resolveExport: ((value: { file_name: string; content: string }) => void) | null = null;
    exportSessionMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveExport = resolve;
        }),
    );

    render(<SessionSidebar sessionId="session-1" />);

    await screen.findByRole("button", { name: "打开会话 产品调研" });

    fireEvent.click(screen.getByRole("button", { name: "导出 PRD" }));

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("正在导出 PRD...");
    });
    expect(screen.getByRole("button", { name: "导出中..." })).toBeDisabled();

    resolveExport?.({
      file_name: "ai-cofounder-prd.md",
      content: "# PRD",
    });

    await waitFor(() => {
      expect(useToastStore.getState().toast?.message).toBe("PRD 已导出");
    });
  });
});
