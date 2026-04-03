import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceEntry } from "../components/workspace/workspace-entry";
import { useToastStore } from "../store/toast-store";

const createSessionMock = vi.fn();
const listSessionsMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", () => ({
  createSession: (...args: unknown[]) => createSessionMock(...args),
  listSessions: (...args: unknown[]) => listSessionsMock(...args),
}));

describe("WorkspaceEntry", () => {
  beforeEach(() => {
    createSessionMock.mockReset();
    listSessionsMock.mockReset();
    pushMock.mockReset();
    useToastStore.getState().clearToast();
    listSessionsMock.mockResolvedValue({ sessions: [] });
  });

  it("creates a new session and redirects into the workspace", async () => {
    createSessionMock.mockResolvedValue({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "产品访谈助手",
        initial_idea: "帮我把零散需求整理成 PRD",
      },
      state: {
        idea: "帮我把零散需求整理成 PRD",
      },
      prd_snapshot: {
        sections: {},
      },
    });

    render(<WorkspaceEntry />);

    fireEvent.change(screen.getByLabelText("会话标题"), {
      target: { value: "产品访谈助手" },
    });
    fireEvent.change(screen.getByLabelText("初始想法"), {
      target: { value: "帮我把零散需求整理成 PRD" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建并进入工作台" }));

    await waitFor(() => {
      expect(createSessionMock).toHaveBeenCalledWith(
        {
          title: "产品访谈助手",
          initial_idea: "帮我把零散需求整理成 PRD",
        },
        null,
      );
      expect(pushMock).toHaveBeenCalledWith("/workspace/session-1");
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
        },
        {
          id: "session-2",
          user_id: "user-1",
          title: "更早的会话",
          initial_idea: "older idea",
        },
      ],
    });

    render(<WorkspaceEntry />);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/workspace/session-3");
    });

    expect(screen.queryByText("最近活跃会话")).not.toBeInTheDocument();
  });

  it("renders the global toast on workspace entry", async () => {
    useToastStore.getState().showToast({
      message: "会话已删除",
      tone: "success",
    });

    render(<WorkspaceEntry />);

    expect(await screen.findByText("会话已删除")).toBeInTheDocument();
  });
});
