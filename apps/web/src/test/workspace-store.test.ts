import { describe, expect, it } from "vitest";

import { parseEventStream } from "../lib/sse";
import { createWorkspaceStore } from "../store/workspace-store";

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
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        delta: "先继续明确他们最痛的一次产品决策卡点。",
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
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
      },
    });
    store.getState().markInterrupted();

    expect(store.getState().lastInterrupted).toBe(true);
  });

  it("replays the last accepted user input without duplicating the user message", () => {
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
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
      },
    });
    const regenerateInput = store.getState().startRegenerate();
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-2",
      },
    });

    expect(regenerateInput).toBe(true);
    expect(store.getState().messages.filter((message) => message.role === "user")).toHaveLength(1);
    expect(store.getState().messages.at(-1)?.role).toBe("user");
  });

  it("clears the interrupted marker when a new request starts", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
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
        delta: "继续往下收敛。",
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
    });

    expect(store.getState().inputValue).toBe("");
    expect(store.getState().messages).toHaveLength(2);
    expect(store.getState().messages[0]).toMatchObject({ role: "user", content: "你好" });
    expect(store.getState().messages[1]).toMatchObject({
      role: "assistant",
      content: "你好，请问你的想法是？",
    });
    expect(store.getState().currentAction).toBeNull();
    expect(store.getState().isStreaming).toBe(false);
    expect(store.getState().pendingUserInput).toBeNull();
    expect(store.getState().lastInterrupted).toBe(false);
    expect(store.getState().lastSubmittedInput).toBeNull();
    expect(store.getState().prd.sections.target_user?.content).toBe("独立开发者");
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
