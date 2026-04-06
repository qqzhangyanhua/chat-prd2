import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getSession } from "../lib/api";

import { WorkspaceSessionShell } from "../components/workspace/workspace-session-shell";
import { useToastStore } from "../store/toast-store";
import { workspaceStore } from "../store/workspace-store";

const getSessionMock = vi.fn();
const listEnabledModelConfigsMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", () => ({
  getSession: (...args: unknown[]) => getSessionMock(...args),
  listEnabledModelConfigs: (...args: unknown[]) => listEnabledModelConfigsMock(...args),
}));

describe("WorkspaceSessionShell", () => {
  beforeEach(() => {
    getSessionMock.mockReset();
    listEnabledModelConfigsMock.mockReset();
    pushMock.mockReset();
    window.sessionStorage.clear();
    useToastStore.getState().clearToast();
    workspaceStore.setState(workspaceStore.getInitialState(), true);
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
      assistant_reply_groups: [],
    });
    listEnabledModelConfigsMock.mockResolvedValue({
      items: [
        {
          id: "model-openai",
          name: "OpenAI GPT-4.1",
          model: "gpt-4.1",
        },
      ],
    });
  });

  it("loads the current session snapshot on mount", async () => {
    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledWith("session-1", null);
    });
  });

  it("loads enabled model configs on mount and writes them into the store", async () => {
    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(listEnabledModelConfigsMock).toHaveBeenCalledWith(null);
    });

    expect(workspaceStore.getState().availableModelConfigs).toEqual([
      {
        id: "model-openai",
        name: "OpenAI GPT-4.1",
        model: "gpt-4.1",
      },
    ]);
    expect(workspaceStore.getState().selectedModelConfigId).toBe("model-openai");
  });

  it("hydrates a pending new-session draft into the composer input and clears it", async () => {
    window.sessionStorage.setItem(
      "ai-cofounder:new-session-draft:session-1",
      "这是在入口页写好的长文本草稿",
    );

    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledWith("session-1", null);
    });

    await waitFor(() => {
      expect(workspaceStore.getState().inputValue).toBe("这是在入口页写好的长文本草稿");
    });

    expect(
      window.sessionStorage.getItem("ai-cofounder:new-session-draft:session-1"),
    ).toBeNull();
  });

  it("keeps the workspace usable when session loading succeeds but model loading fails", async () => {
    listEnabledModelConfigsMock.mockRejectedValue(new Error("模型列表加载失败"));

    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledWith("session-1", null);
    });

    await waitFor(() => {
      expect(workspaceStore.getState().currentAction).toBeNull();
    });

    expect(workspaceStore.getState().messages).toEqual([]);
    expect(workspaceStore.getState().availableModelConfigs).toEqual([]);
    expect(workspaceStore.getState().selectedModelConfigId).toBeNull();
    expect(screen.queryByRole("button", { name: "重试加载" })).not.toBeInTheDocument();
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

  it("does not render stale workspace content when the session fails to load", async () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      messages: [
        {
          id: "stale-message",
          role: "assistant",
          content: "这是旧会话残留的回复",
        },
      ],
      prd: {
        sections: {
          target_user: {
            title: "目标用户",
            content: "这是旧会话残留的 PRD",
            status: "confirmed",
          },
        },
      },
    });
    getSessionMock.mockRejectedValue(new Error("会话加载失败"));

    render(<WorkspaceSessionShell sessionId="session-1" />);

    await screen.findByRole("button", { name: "重试加载" });

    expect(screen.queryByText("这是旧会话残留的回复")).not.toBeInTheDocument();
    expect(screen.queryByText("这是旧会话残留的 PRD")).not.toBeInTheDocument();
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
      assistant_reply_groups: [],
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
        assistant_reply_groups: [],
      });

    render(<WorkspaceSessionShell sessionId="session-1" />);

    const retryButton = await screen.findByRole("button", { name: "重试加载" });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledTimes(2);
    });
  });

  it("restores the retry button after a retry also fails", async () => {
    getSessionMock
      .mockRejectedValueOnce(new Error("首次加载失败"))
      .mockRejectedValueOnce(new Error("重试仍失败"));

    render(<WorkspaceSessionShell sessionId="session-1" />);

    const retryButton = await screen.findByRole("button", { name: "重试加载" });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByRole("button", { name: "重试加载" })).toBeEnabled();
  });

  it("hydrates assistant reply groups into workspace store", async () => {
    getSessionMock.mockResolvedValueOnce({
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
      assistant_reply_groups: [
        {
          id: "group-1",
          session_id: "session-1",
          user_message_id: "user-1",
          latest_version_id: "version-2",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
          versions: [
            {
              id: "version-1",
              reply_group_id: "group-1",
              session_id: "session-1",
              user_message_id: "user-1",
              version_no: 1,
              content: "第一版",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 2,
              created_at: "2026-04-05T00:00:00Z",
            },
            {
              id: "version-2",
              reply_group_id: "group-1",
              session_id: "session-1",
              user_message_id: "user-1",
              version_no: 2,
              content: "第二版",
              action_snapshot: {},
              model_meta: {},
              state_version_id: null,
              prd_snapshot_version: 3,
              created_at: "2026-04-05T00:00:00Z",
            },
          ],
        },
      ],
    });

    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(workspaceStore.getState().replyGroups["group-1"]?.latestVersionId).toBe("version-2");
    });
  });
});
