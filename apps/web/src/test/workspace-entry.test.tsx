import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceEntry } from "../components/workspace/workspace-entry";
import { useToastStore } from "../store/toast-store";

const createSessionMock = vi.fn();
const getHealthStatusMock = vi.fn();
const listSessionsMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", () => ({
  createSession: (...args: unknown[]) => createSessionMock(...args),
  getHealthStatus: (...args: unknown[]) => getHealthStatusMock(...args),
  listSessions: (...args: unknown[]) => listSessionsMock(...args),
  SCHEMA_OUTDATED_DETAIL: "数据库结构版本过旧，请先执行 alembic upgrade head",
}));

vi.mock("../store/auth-store", () => ({
  useAuthStore: vi.fn(),
}));

vi.mock("../hooks/use-auth-guard", () => ({
  useAuthGuard: vi.fn(() => ({ hydrated: true })),
}));

import { useAuthStore } from "../store/auth-store";

describe("WorkspaceEntry", () => {
  beforeEach(() => {
    createSessionMock.mockReset();
    getHealthStatusMock.mockReset();
    listSessionsMock.mockReset();
    pushMock.mockReset();
    window.sessionStorage.clear();
    useToastStore.getState().clearToast();
    listSessionsMock.mockResolvedValue({ sessions: [] });
    vi.mocked(useAuthStore).mockImplementation((selector) =>
      selector({
        accessToken: null,
        user: null,
        isAuthenticated: false,
        setAuth: vi.fn(),
        clearAuth: vi.fn(),
      } as never),
    );
  });

  it("shows an explicit migration hint when backend schema is outdated", async () => {
    listSessionsMock.mockRejectedValue(
      new Error("数据库结构版本过旧，请先执行 alembic upgrade head"),
    );
    getHealthStatusMock.mockResolvedValue({
      status: "degraded",
      schema: "outdated",
      detail: "数据库结构版本过旧，请先执行 alembic upgrade head",
      missing_tables: ["agent_turn_decisions", "assistant_reply_versions"],
    });

    render(<WorkspaceEntry />);

    expect(await screen.findByText("后端数据库迁移未完成")).toBeInTheDocument();
    expect(screen.getByText("agent_turn_decisions")).toBeInTheDocument();
    expect(screen.getByText("assistant_reply_versions")).toBeInTheDocument();
    expect(screen.getByText(/cd apps\/api && alembic upgrade head/i)).toBeInTheDocument();
  });

  it("creates a new session and redirects into the workspace", async () => {
    createSessionMock.mockResolvedValue({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "产品访谈助手",
        initial_idea: "帮我把零散需求整理成 PRD",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        idea: "帮我把零散需求整理成 PRD",
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
    });

    render(<WorkspaceEntry />);

    await screen.findByText("Describe your idea");

    fireEvent.change(
      screen.getByPlaceholderText(
        "Tell me about your product idea, the problem you're solving, or what you want to build...",
      ),
      {
        target: { value: "帮我把零散需求整理成 PRD" },
      },
    );
    fireEvent.change(screen.getByPlaceholderText("Project name (optional)"), {
      target: { value: "产品访谈助手" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start Session" }));

    await waitFor(() => {
      expect(createSessionMock).toHaveBeenCalledWith(
        {
          title: "产品访谈助手",
          initial_idea: "帮我把零散需求整理成 PRD",
        },
        null,
      );
      expect(
        window.sessionStorage.getItem("ai-cofounder:new-session-draft:session-1"),
      ).toBe("帮我把零散需求整理成 PRD");
      expect(pushMock).toHaveBeenCalledWith("/workspace?session=session-1");
    });
  });

  it("redirects to the latest session when sessions already exist", async () => {
    listSessionsMock.mockResolvedValue({
      sessions: [
        {
          id: "session-3",
          user_id: "user-1",
          title: "最近活跃会话",
          initial_idea: "idea",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
        },
        {
          id: "session-2",
          user_id: "user-1",
          title: "更早的会话",
          initial_idea: "older idea",
          created_at: "2026-04-04T00:00:00Z",
          updated_at: "2026-04-04T00:00:00Z",
        },
      ],
    });

    render(<WorkspaceEntry />);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/workspace?session=session-3");
    });
  });

  it("does not redirect to the latest session when auto redirect is disabled", async () => {
    listSessionsMock.mockResolvedValue({
      sessions: [
        {
          id: "session-3",
          user_id: "user-1",
          title: "最近活跃会话",
          initial_idea: "idea",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
        },
      ],
    });

    render(<WorkspaceEntry autoRedirectToLatest={false} />);

    expect(await screen.findByText("Describe your idea")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders the global toast on workspace entry", async () => {
    useToastStore.getState().showToast({
      message: "会话已删除",
      tone: "success",
    });

    render(<WorkspaceEntry />);

    expect(await screen.findByText("会话已删除")).toBeInTheDocument();
  });

  it("clicks 'Product Discovery' chip to pre-fill idea textarea", async () => {
    listSessionsMock.mockResolvedValue({ sessions: [] });
    render(<WorkspaceEntry />);

    await screen.findByText("Describe your idea");

    const buttons = screen.getAllByRole("button", { name: /product discovery/i });
    fireEvent.click(buttons[buttons.length - 1]);

    const textarea = screen.getByPlaceholderText(/tell me about your product idea/i);
    expect(textarea).toHaveValue("我有一个产品想法，想通过对话挖掘用户需求和核心问题。");
  });

  it("clicks 'Feature Planning' chip to pre-fill idea textarea", async () => {
    listSessionsMock.mockResolvedValue({ sessions: [] });
    render(<WorkspaceEntry />);

    await screen.findByText("Describe your idea");

    const buttons = screen.getAllByRole("button", { name: /feature planning/i });
    fireEvent.click(buttons[buttons.length - 1]);

    const textarea = screen.getByPlaceholderText(/tell me about your product idea/i);
    expect(textarea).toHaveValue("我需要为现有产品规划新功能，梳理优先级和实现路径。");
  });

  it("logs out when logout button is clicked", async () => {
    const clearAuthMock = vi.fn();
    vi.mocked(useAuthStore).mockImplementation((selector) =>
      selector({
        accessToken: null,
        user: null,
        isAuthenticated: false,
        setAuth: vi.fn(),
        clearAuth: clearAuthMock,
      } as never),
    );
    listSessionsMock.mockResolvedValue({ sessions: [] });

    render(<WorkspaceEntry />);

    await screen.findByText("Describe your idea");

    const menuButton = screen.getByRole("button", { name: /more/i });
    fireEvent.click(menuButton);

    const logoutBtn = await screen.findByRole("button", { name: /退出登录/i });
    fireEvent.click(logoutBtn);

    expect(clearAuthMock).toHaveBeenCalled();
    expect(pushMock).toHaveBeenCalledWith("/login");
  });
});
