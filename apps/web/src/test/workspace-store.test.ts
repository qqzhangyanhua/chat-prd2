import { describe, expect, it } from "vitest";

import type { AgentTurnDecision, SessionSnapshotResponse } from "../lib/types";
import { parseEventStream } from "../lib/sse";
import { createWorkspaceStore } from "../store/workspace-store";

function buildSnapshotWithDecisions(decisions?: AgentTurnDecision[]): SessionSnapshotResponse {
  return {
    session: {
      id: "session-1",
      user_id: "user-1",
      title: "AI Co-founder",
      initial_idea: "idea",
      created_at: "2026-04-05T00:00:00Z",
      updated_at: "2026-04-05T00:00:00Z",
    },
    state: {},
    prd_snapshot: {
      sections: {},
    },
    messages: [],
    assistant_reply_groups: [],
    turn_decisions: decisions,
  };
}

describe("workspace store", () => {
  it("updates prd panel when prd.updated event arrives", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {
          target_user: {
            content: "独立开发者仍然是当前最优先的一类目标用户。",
            status: "inferred",
            title: "目标用户",
          },
        },
      },
    });

    expect(store.getState().prd.sections.target_user?.content).toBe(
      "独立开发者仍然是当前最优先的一类目标用户。",
    );
  });

  it("appends assistant delta into the active assistant message", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-1",
        session_id: "session-1",
      },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先继续明确他们最痛的一次产品决策卡点。",
        is_regeneration: false,
        is_latest: false,
      },
    });

    expect(store.getState().messages.at(-1)?.content).toBe(
      "先继续明确他们最痛的一次产品决策卡点。",
    );
    expect(store.getState().messages.at(-1)?.role).toBe("assistant");
  });

  it("records the latest accepted user input for regeneration", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-1",
        session_id: "session-1",
      },
    });

    expect(store.getState().lastSubmittedInput).toBe("我想先服务独立开发者");
  });

  it("marks the latest assistant draft as interrupted after manual cancel", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().markInterrupted();

    expect(store.getState().lastInterrupted).toBe(true);
  });

  it("starts regenerate without removing the last assistant message", () => {
    const store = createWorkspaceStore();
    store.getState().setAvailableModelConfigs([
      {
        id: "model-openai",
        name: "OpenAI GPT-4.1",
        model: "gpt-4.1",
      },
    ]);

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-1",
        session_id: "session-1",
      },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_id: "version-1",
        version_no: 1,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        is_regeneration: false,
        is_latest: true,
        message_id: "assistant-1",
      },
    });
    const regenerateInput = store.getState().startRegenerate();

    expect(regenerateInput).toBe(true);
    expect(store.getState().messages.filter((message) => message.role === "user")).toHaveLength(1);
    expect(store.getState().messages.at(-1)?.role).toBe("assistant");
  });

  it("clears the interrupted marker when a new request starts", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().markInterrupted();

    store.getState().startRequest("继续往下问");

    expect(store.getState().lastInterrupted).toBe(false);
  });

  it("clears inputValue immediately when a request is started", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想服务独立开发者");

    expect(store.getState().inputValue).toBe("");
  });

  it("hydrates a recovered session and loads messages from snapshot", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("继续追问");
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "继续往下收敛。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().markInterrupted();

    store.getState().hydrateSession({
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
          id: "m1",
          session_id: "session-1",
          role: "user",
          content: "你好",
          message_type: "chat",
        },
        {
          id: "m2",
          session_id: "session-1",
          role: "assistant",
          content: "你好，请问你的想法是？",
          message_type: "chat",
        },
      ],
      assistant_reply_groups: [],
    });

    expect(store.getState().inputValue).toBe("");
    expect(store.getState().messages).toHaveLength(2);
    expect(store.getState().messages[0]).toMatchObject({ role: "user", content: "你好" });
    expect(store.getState().messages[1]).toMatchObject({
      role: "assistant",
      content: "你好，请问你的想法是？",
    });
    expect(store.getState().replyGroups).toEqual({});
    expect(store.getState().selectedHistoryGroupId).toBeNull();
    expect(store.getState().selectedHistoryVersionId).toBeNull();
    expect(store.getState().currentAction).toBeNull();
    expect(store.getState().isStreaming).toBe(false);
    expect(store.getState().pendingUserInput).toBeNull();
    expect(store.getState().lastInterrupted).toBe(false);
    expect(store.getState().lastSubmittedInput).toBeNull();
    expect(store.getState().prd.sections.target_user?.content).toBe("独立开发者");
  });

  it("hydrates legacy snapshot when assistant_reply_groups is missing", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
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
      messages: [
        {
          id: "user-1",
          session_id: "session-1",
          role: "user",
          content: "你好",
          message_type: "chat",
        },
      ],
    });

    expect(store.getState().messages).toHaveLength(1);
    expect(store.getState().replyGroups).toEqual({});
  });

  it("refreshes session snapshot without clearing current action or typed input", () => {
    const store = createWorkspaceStore();

    store.setState({
      ...store.getState(),
      currentAction: {
        action: "probe_deeper",
        target: "problem",
        reason: "继续澄清问题边界",
      },
      inputValue: "我已经开始输入下一条了",
      lastSubmittedInput: "上一轮输入",
      isStreaming: false,
    });

    store.getState().refreshSessionSnapshot({
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
      messages: [
        {
          id: "user-1",
          session_id: "session-1",
          role: "user",
          content: "上一轮用户输入",
          message_type: "chat",
        },
        {
          id: "assistant-1",
          session_id: "session-1",
          role: "assistant",
          content: "刷新后的回复",
          message_type: "chat",
        },
      ],
      assistant_reply_groups: [],
      turn_decisions: [
        {
          id: "decision-1",
          session_id: "session-1",
          created_at: "2026-04-07T10:00:00Z",
          state_patch_json: {
            conversation_strategy: "confirm",
            strategy_reason: "需要确认最新范围",
            next_best_questions: ["确认下一步优先级"],
          },
        },
      ],
    });

    expect(store.getState().currentAction).toEqual({
      action: "probe_deeper",
      target: "problem",
      reason: "继续澄清问题边界",
    });
    expect(store.getState().inputValue).toBe("我已经开始输入下一条了");
    expect(store.getState().lastSubmittedInput).toBe("上一轮输入");
    expect(store.getState().messages.at(-1)?.content).toBe("刷新后的回复");
    expect(store.getState().decisionGuidance?.strategyLabel).toBe("确认中");
  });

  it("resets prd sections when the loaded session has an empty snapshot", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {
          target_user: {
            title: "目标用户",
            content: "上一会话的目标用户",
            status: "confirmed",
          },
        },
      },
    });

    store.getState().hydrateSession({
      session: {
        id: "session-2",
        user_id: "user-1",
        title: "新的空白会话",
        initial_idea: "new idea",
        created_at: "2026-04-06T00:00:00Z",
        updated_at: "2026-04-06T00:00:00Z",
      },
      state: {
        idea: "new idea",
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
    });

    expect(store.getState().prd.sections.target_user?.content).not.toBe("上一会话的目标用户");
    expect(store.getState().prd.sections.target_user?.content).toBe(
      "还需要继续明确谁会最频繁、最迫切地使用这个产品。",
    );
  });

  it("stores reply groups and keeps old versions when regenerate completes", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: { message_id: "user-1", session_id: "session-1" },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "第一版",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_id: "version-1",
        version_no: 1,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        is_regeneration: false,
        is_latest: true,
        message_id: "assistant-1",
      },
    });

    store.getState().startRegenerate();
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        delta: "第二版",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 3,
        is_regeneration: true,
        is_latest: true,
      },
    });

    const group = store.getState().replyGroups["group-1"];
    expect(group).toBeDefined();
    expect(group.latestVersionId).toBe("version-2");
    expect(group.versions.map((version) => version.id)).toEqual(["version-1", "version-2"]);
    expect(group.versions[0].isLatest).toBe(false);
    expect(group.versions[1].isLatest).toBe(true);
    expect(store.getState().selectedHistoryGroupId).toBe("group-1");
    expect(store.getState().selectedHistoryVersionId).toBe("version-2");
    expect(store.getState().messages.at(-1)?.content).toBe("第二版");
  });

  it("updates the visible assistant card after regenerate on a hydrated session", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
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
      messages: [
        {
          id: "user-1",
          session_id: "session-1",
          role: "user",
          content: "你好",
          message_type: "chat",
        },
        {
          id: "version-1",
          session_id: "session-1",
          role: "assistant",
          content: "第一版",
          message_type: "chat",
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
              content: "第一版",
              action_snapshot: {},
              model_meta: {},
              state_version_id: "state-1",
              prd_snapshot_version: 1,
              created_at: "2026-04-05T00:00:00Z",
              is_latest: true,
            },
          ],
        },
      ],
    });

    store.getState().startRegenerate();
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-mirror-1",
        model_config_id: "model-openai",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-mirror-1",
        model_config_id: "model-openai",
        delta: "第二版",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-mirror-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        is_regeneration: true,
        is_latest: true,
      },
    });

    expect(store.getState().messages.at(-1)).toMatchObject({
      id: "version-2",
      content: "第二版",
      replyGroupId: "group-1",
      versionNo: 2,
      isLatest: true,
    });
  });

  it("ignores stale assistant.done events for an older active version", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: { message_id: "user-1", session_id: "session-1" },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_id: "version-1",
        version_no: 1,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        is_regeneration: true,
        is_latest: true,
      },
    });

    expect(store.getState().activeAssistantVersionId).toBe("version-2");
    expect(store.getState().replyGroups["group-1"]?.latestVersionId).not.toBe("version-1");
  });
});

describe("decision guidance", () => {
  it("hydrates guidance from judgement and next_step sections", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-1",
        session_id: "session-1",
        created_at: "2026-04-07T10:00:00Z",
        decision_sections: [
          {
            key: "judgement",
            meta: {
              conversation_strategy: "converge",
              strategy_label: "收敛中",
              strategy_reason: "先收敛核心假设",
            },
          },
          {
            key: "next_step",
            meta: {
              next_best_questions: ["如果只能选一个主线怎么办？", "请告诉我下一步动作"],
            },
          },
        ],
        state_patch_json: {
          conversation_strategy: "choose",
          strategy_reason: "不应该使用",
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "converge",
      strategyLabel: "收敛中",
      strategyReason: "先收敛核心假设",
      nextBestQuestions: [
        "如果只能选一个主线怎么办？",
        "请告诉我下一步动作",
      ],
    });
  });

  it("falls back to state_patch_json when sections are incomplete and prefers judgement reason", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-2",
        session_id: "session-1",
        created_at: "2026-04-07T11:00:00Z",
        decision_sections: [
          {
            key: "judgement",
            meta: {
              strategy_reason: "判断来自 meta",
            },
          },
        ],
        state_patch_json: {
          conversation_strategy: "choose",
          next_best_questions: [
            " 先明确主线 ",
            "再问对方的关键指标",
            "再问对方的关键指标",
            "",
            "再确认细节",
          ],
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "choose",
      strategyLabel: "取舍中",
      strategyReason: "判断来自 meta",
      nextBestQuestions: [
        "先明确主线",
        "再问对方的关键指标",
        "再确认细节",
      ],
    });
  });

  it("selects the latest decision by created_at and falls back to the last entry when timestamps are invalid", () => {
    const newestStore = createWorkspaceStore();
    const newestSnapshot = buildSnapshotWithDecisions([
      {
        id: "decision-old",
        session_id: "session-1",
        created_at: "2026-04-07T09:00:00Z",
        state_patch_json: {
          conversation_strategy: "clarify",
          strategy_reason: "老决策",
          next_best_questions: ["老推荐"],
        },
      },
      {
        id: "decision-new",
        session_id: "session-1",
        created_at: "2026-04-07T12:00:00Z",
        decision_sections: [
          {
            key: "judgement",
            meta: {
              conversation_strategy: "confirm",
              strategy_label: "确认中",
              strategy_reason: "最新决策",
            },
          },
          {
            key: "next_step",
            meta: {
              next_best_questions: ["请确认这个需求清单"],
            },
          },
        ],
      },
    ]);

    newestStore.getState().hydrateSession(newestSnapshot);
    expect(newestStore.getState().decisionGuidance?.strategyReason).toBe("最新决策");
    expect(newestStore.getState().decisionGuidance?.conversationStrategy).toBe("confirm");

    const mixStore = createWorkspaceStore();
    const mixSnapshot = buildSnapshotWithDecisions([
      {
        id: "decision-mix-old",
        session_id: "session-1",
        created_at: null,
        state_patch_json: {
          conversation_strategy: "clarify",
          strategy_reason: "不带时间戳",
        },
      },
      {
        id: "decision-mix-new",
        session_id: "session-1",
        created_at: "2026-04-07T20:00:00Z",
        state_patch_json: {
          conversation_strategy: "converge",
          strategy_reason: "最新时间",
          next_best_questions: ["继续推进"],
        },
      },
    ]);

    mixStore.getState().hydrateSession(mixSnapshot);
    expect(mixStore.getState().decisionGuidance?.strategyReason).toBe("最新时间");

    const fallbackStore = createWorkspaceStore();
    const fallbackSnapshot = buildSnapshotWithDecisions([
      {
        id: "decision-invalid",
        session_id: "session-1",
        created_at: "not-a-date",
        state_patch_json: {
          conversation_strategy: "choose",
          strategy_reason: "坏时间戳",
          next_best_questions: ["从最后一个决策"],
        },
      },
      {
        id: "decision-last",
        session_id: "session-1",
        state_patch_json: {
          conversation_strategy: "converge",
          strategy_reason: "数组尾部",
          next_best_questions: ["优先参考最后一条"],
        },
        decision_sections: [
          {
            key: "next_step",
            meta: {
              next_best_questions: ["优先参考最后一条"],
            },
          },
        ],
      },
    ]);

    fallbackStore.getState().hydrateSession(fallbackSnapshot);
    expect(fallbackStore.getState().decisionGuidance?.strategyReason).toBe("数组尾部");
  });

  it("chooses last entry when final decision lacks a valid created_at", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-old-valid",
        session_id: "session-1",
        created_at: "2026-04-07T08:00:00Z",
        state_patch_json: {
          conversation_strategy: "clarify",
          strategy_reason: "有效时间",
        },
      },
      {
        id: "decision-last-bad",
        session_id: "session-1",
        created_at: "not-a-date",
        state_patch_json: {
          conversation_strategy: "converge",
          strategy_reason: "最后一条",
          next_best_questions: ["看最后"],
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);
    expect(store.getState().decisionGuidance?.strategyReason).toBe("最后一条");
  });

  it("normalizes next best questions, filters/reduces duplicates, and defaults strategy values", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-normalize",
        session_id: "session-1",
        created_at: "2026-04-07T13:00:00Z",
        state_patch_json: {
          next_best_questions: [
            " 先问对方的关键指标  ",
            "",
            "先问对方的关键指标",
            "再确认痛点",
            "再确认预算",
            "再确认交付",
            "保持开放",
          ],
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "clarify",
      strategyLabel: "澄清中",
      strategyReason: null,
      nextBestQuestions: [
        "先问对方的关键指标",
        "再确认痛点",
        "再确认预算",
        "再确认交付",
      ],
    });
  });

  it("drops non-string recommendations instead of throwing", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-non-string",
        session_id: "session-1",
        created_at: "2026-04-07T16:00:00Z",
        state_patch_json: {
          next_best_questions: [
            "可用问题",
            null,
            42,
            { text: "结构体" },
            "最后一个",
          ],
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance?.nextBestQuestions).toEqual([
      "可用问题",
      "最后一个",
    ]);
  });

  it("does not generate guidance when normalized recommendations are empty", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-empty",
        session_id: "session-1",
        created_at: "2026-04-07T14:00:00Z",
        state_patch_json: {
          next_best_questions: ["", "   "],
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toBeNull();
  });
});

describe("parseEventStream", () => {
  it("parses sse chunks into typed events", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: action.decided\ndata: {"action":"probe_deeper","target":"target_user","reason":"继续追问目标用户"}\n\n' +
              'event: assistant.delta\ndata: {"delta":"先把目标用户再缩窄一层。"}\n\n',
          ),
        );
        controller.close();
      },
    });

    const events = [];
    for await (const event of parseEventStream(stream)) {
      events.push(event);
    }

    expect(events).toEqual([
      {
        type: "action.decided",
        data: {
          action: "probe_deeper",
          target: "target_user",
          reason: "继续追问目标用户",
        },
      },
      {
        type: "assistant.delta",
        data: {
          delta: "先把目标用户再缩窄一层。",
        },
      },
    ]);
  });
});
