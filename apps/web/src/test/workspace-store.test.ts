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

  it("hydrates a recovered session as a consistent fresh snapshot", () => {
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
    });

    expect(store.getState().inputValue).toBe("idea");
    expect(store.getState().messages).toEqual([]);
    expect(store.getState().currentAction).toBeNull();
    expect(store.getState().isStreaming).toBe(false);
    expect(store.getState().pendingUserInput).toBeNull();
    expect(store.getState().lastInterrupted).toBe(false);
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
