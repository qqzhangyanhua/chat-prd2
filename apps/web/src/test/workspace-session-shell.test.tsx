import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceSessionShell } from "../components/workspace/workspace-session-shell";
import { useToastStore } from "../store/toast-store";
import { workspaceStore } from "../store/workspace-store";

const getSessionMock = vi.fn();
const getHealthStatusMock = vi.fn();
const listEnabledModelConfigsMock = vi.fn();
const sendMessageMock = vi.fn();
const regenerateMessageMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", () => ({
  getHealthStatus: (...args: unknown[]) => getHealthStatusMock(...args),
  getSession: (...args: unknown[]) => getSessionMock(...args),
  listEnabledModelConfigs: (...args: unknown[]) => listEnabledModelConfigsMock(...args),
  sendMessage: (...args: unknown[]) => sendMessageMock(...args),
  regenerateMessage: (...args: unknown[]) => regenerateMessageMock(...args),
  SCHEMA_OUTDATED_DETAIL: "数据库结构版本过旧，请先执行 alembic upgrade head",
}));

vi.mock("../hooks/use-auth-guard", () => ({
  useAuthGuard: vi.fn(() => ({ hydrated: true })),
}));

vi.mock("../hooks/use-schema-gate", () => ({
  useSchemaGate: vi.fn(() => ({
    schemaHealth: null,
    clearSchemaHealth: vi.fn(),
    checkSchemaGate: vi.fn(),
    isCheckingSchema: false,
    syncSchemaFromError: vi.fn(),
  })),
}));

vi.mock("../store/auth-store", () => ({
  useAuthStore: vi.fn((selector) =>
    selector({
      accessToken: null,
      user: null,
      isAuthenticated: false,
      setAuth: vi.fn(),
      clearAuth: vi.fn(),
    }),
  ),
}));

describe("WorkspaceSessionShell", () => {
  beforeEach(() => {
    getSessionMock.mockReset();
    getHealthStatusMock.mockReset();
    listEnabledModelConfigsMock.mockReset();
    sendMessageMock.mockReset();
    regenerateMessageMock.mockReset();
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
        extraSections: {},
        meta: workspaceStore.getInitialState().prd.meta,
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

  it("uses the shared error notice in both conversation and PRD columns when session loading fails", async () => {
    getSessionMock.mockRejectedValue(new Error("会话加载失败"));

    render(<WorkspaceSessionShell sessionId="session-1" />);

    expect(await screen.findByRole("button", { name: "重试加载" })).toBeInTheDocument();
    expect(screen.getByText("当前会话加载失败，暂不展示 PRD 快照。")).toBeInTheDocument();
    expect(screen.getAllByTestId("workspace-error-notice")).toHaveLength(2);
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

  it("uses structured recovery action when session snapshot is missing", async () => {
    getSessionMock.mockRejectedValue(
      Object.assign(new Error("Session snapshot not found"), {
        code: "SESSION_SNAPSHOT_MISSING",
        recoveryAction: {
          type: "open_workspace_home",
          label: "返回工作台首页",
          target: "/workspace",
        },
      }),
    );

    render(<WorkspaceSessionShell sessionId="session-1" />);

    const actionButton = await screen.findByRole("button", { name: "返回工作台首页" });
    fireEvent.click(actionButton);

    expect(pushMock).toHaveBeenCalledWith("/workspace/home");
  });

  it("shows an explicit migration hint when session loading fails because schema is outdated", async () => {
    getSessionMock.mockRejectedValue(
      new Error("数据库结构版本过旧，请先执行 alembic upgrade head"),
    );
    getHealthStatusMock.mockResolvedValue({
      status: "degraded",
      schema: "outdated",
      detail: "数据库结构版本过旧，请先执行 alembic upgrade head",
      error: {
        code: "SCHEMA_OUTDATED",
        message: "数据库结构版本过旧，请先执行 alembic upgrade head",
        recovery_action: {
          type: "run_migration",
          label: "执行数据库迁移",
          target: "cd apps/api && uv run alembic upgrade head",
        },
      },
      missing_tables: ["agent_turn_decisions"],
    });

    render(<WorkspaceSessionShell sessionId="session-1" />);

    expect(await screen.findByText("后端数据库迁移未完成")).toBeInTheDocument();
    expect(screen.getByText("agent_turn_decisions")).toBeInTheDocument();
    expect(screen.getByText(/cd apps\/api && uv run alembic upgrade head/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新检测" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重试加载" })).not.toBeInTheDocument();
  });

  it("re-checks schema status and reloads the session when migration is fixed", async () => {
    getSessionMock
      .mockRejectedValueOnce(new Error("数据库结构版本过旧，请先执行 alembic upgrade head"))
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
    getHealthStatusMock
      .mockResolvedValueOnce({
        status: "degraded",
        schema: "outdated",
        detail: "数据库结构版本过旧，请先执行 alembic upgrade head",
        missing_tables: ["agent_turn_decisions"],
      })
      .mockResolvedValueOnce({
        status: "ok",
        schema: "ready",
      });

    render(<WorkspaceSessionShell sessionId="session-1" />);

    const retryButton = await screen.findByRole("button", { name: "重新检测" });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getHealthStatusMock).toHaveBeenCalledTimes(2);
      expect(getSessionMock).toHaveBeenCalledTimes(2);
      expect(screen.queryByText("后端数据库迁移未完成")).not.toBeInTheDocument();
    });
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

  it("refreshes the PRD panel after regenerate emits prd.updated", async () => {
    const encoder = new TextEncoder();
    getSessionMock
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
          sections: {
            target_user: {
              title: "目标用户",
              content: "独立开发者",
              status: "confirmed",
            },
          },
        },
        messages: [
          {
            id: "user-1",
            session_id: "session-1",
            role: "user",
            content: "请给我一个版本",
            message_type: "text",
            reply_group_id: null,
            version_no: null,
            is_latest: true,
          },
          {
            id: "assistant-1",
            session_id: "session-1",
            role: "assistant",
            content: "先给你一个初版。",
            message_type: "text",
            reply_group_id: "group-1",
            version_no: 1,
            is_latest: true,
          },
        ],
        assistant_reply_groups: [
          {
            id: "group-1",
            session_id: "session-1",
            user_message_id: "user-1",
            latest_version_id: "version-1",
            created_at: "2026-04-05T00:00:00Z",
            updated_at: "2026-04-05T00:00:00Z",
            versions: [
              {
                id: "version-1",
                reply_group_id: "group-1",
                session_id: "session-1",
                user_message_id: "user-1",
                version_no: 1,
                content: "先给你一个初版。",
                action_snapshot: {},
                model_meta: {},
                state_version_id: null,
                prd_snapshot_version: 2,
                created_at: "2026-04-05T00:00:00Z",
                is_latest: true,
              },
            ],
          },
        ],
      })
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
          workflow_stage: "refine_loop",
          prd_draft: {
            version: 2,
            status: "draft_refined",
            sections: {
              solution: {
                title: "解决方案",
                content: "重生成后采用浏览器预览加评论分享。",
                status: "confirmed",
              },
              constraints: {
                title: "约束条件",
                content: "首版只支持浏览器端。",
                status: "confirmed",
              },
            },
          },
        },
        prd_snapshot: {
          sections: {
            target_user: {
              title: "目标用户",
              content: "独立开发者",
              status: "confirmed",
            },
            solution: {
              title: "解决方案",
              content: "重生成后采用浏览器预览加评论分享。",
              status: "confirmed",
            },
          },
        },
        messages: [
          {
            id: "user-1",
            session_id: "session-1",
            role: "user",
            content: "请给我一个版本",
            message_type: "text",
            reply_group_id: null,
            version_no: null,
            is_latest: true,
          },
          {
            id: "assistant-1",
            session_id: "session-1",
            role: "assistant",
            content: "这是重生成版本",
            message_type: "text",
            reply_group_id: "group-1",
            version_no: 2,
            is_latest: true,
          },
        ],
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
                content: "先给你一个初版。",
                action_snapshot: {},
                model_meta: {},
                state_version_id: null,
                prd_snapshot_version: 2,
                created_at: "2026-04-05T00:00:00Z",
                is_latest: false,
              },
              {
                id: "version-2",
                reply_group_id: "group-1",
                session_id: "session-1",
                user_message_id: "user-1",
                version_no: 2,
                content: "这是重生成版本",
                action_snapshot: {},
                model_meta: {},
                state_version_id: null,
                prd_snapshot_version: 3,
                created_at: "2026-04-05T00:00:00Z",
                is_latest: true,
              },
            ],
          },
        ],
      });
    regenerateMessageMock.mockResolvedValue(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: action.decided\ndata: {"action":"summarize_understanding","target":null,"reason":"继续刷新 PRD"}\n\n' +
                'event: assistant.version.started\ndata: {"session_id":"session-1","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-2","version_no":2,"assistant_message_id":"assistant-1","model_config_id":"model-openai","is_regeneration":true,"is_latest":false}\n\n' +
                'event: assistant.delta\ndata: {"session_id":"session-1","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-2","version_no":2,"assistant_message_id":"assistant-1","model_config_id":"model-openai","delta":"这是重生成版本","is_regeneration":true,"is_latest":false}\n\n' +
                'event: prd.updated\ndata: {"sections":{"solution":{"title":"解决方案","content":"重生成后采用浏览器预览加评论分享。","status":"confirmed"},"constraints":{"title":"约束条件","content":"首版只支持浏览器端。","status":"confirmed"}}}\n\n' +
                'event: assistant.done\ndata: {"session_id":"session-1","user_message_id":"user-1","reply_group_id":"group-1","assistant_version_id":"version-2","version_id":"version-2","version_no":2,"assistant_message_id":"assistant-1","model_config_id":"model-openai","prd_snapshot_version":3,"is_regeneration":true,"is_latest":true}\n\n',
            ),
          );
          controller.close();
        },
      }),
    );

    render(<WorkspaceSessionShell sessionId="session-1" />);

    const regenerateButton = await screen.findByRole("button", { name: "重新生成" });
    fireEvent.click(regenerateButton);

    await waitFor(() => {
      expect(regenerateMessageMock).toHaveBeenCalledTimes(1);
      expect(getSessionMock).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByText("重生成后采用浏览器预览加评论分享。")).toBeInTheDocument();
    expect(screen.getByText("草稿补充")).toBeInTheDocument();
    expect(screen.getByText("首版只支持浏览器端。")).toBeInTheDocument();
  });

  it("hydrates turn decision guidance from the session snapshot", async () => {
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
      assistant_reply_groups: [],
      turn_decisions: [
        {
          id: "decision-1",
          session_id: "session-1",
          created_at: "2026-04-07T10:00:00Z",
          decision_sections: [
            {
              key: "judgement",
              meta: {
                conversation_strategy: "confirm",
                strategy_label: "确认中",
                strategy_reason: "需要先确认边界",
              },
            },
            {
              key: "next_step",
              meta: {
                next_best_questions: [
                  "确认当前目标用户是哪个人群？",
                  "确认下一步验证的关键假设。",
                ],
                confirm_quick_replies: [
                  "确认，继续下一步",
                  "不对，先改目标用户",
                ],
              },
            },
          ],
          state_patch_json: {
            conversation_strategy: "confirm",
            strategy_reason: "回退原因",
            next_best_questions: ["回退推荐"],
          },
        },
      ],
    });

    render(<WorkspaceSessionShell sessionId="session-1" />);

    await waitFor(() => {
      expect(workspaceStore.getState().decisionGuidance).toEqual({
        conversationStrategy: "confirm",
        strategyLabel: "确认中",
        strategyReason: "需要先确认边界",
        nextBestQuestions: [
          "确认当前目标用户是哪个人群？",
          "确认下一步验证的关键假设。",
        ],
        confirmQuickReplies: [
          "确认，继续下一步",
          "不对，先改目标用户",
        ],
      });
    });
  });
});
