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
            content: "聚焦目标用户还不清晰的独立开发者",
            status: "inferred",
            title: "目标用户",
          },
        },
      },
    });

    expect(store.getState().prd.sections.target_user?.content).toBe(
      "聚焦目标用户还不清晰的独立开发者",
    );
  });

  it("appends assistant delta into the active assistant message", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("帮我收窄目标用户");
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-1",
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        delta: "先收窄目标用户，再讨论 MVP。",
      },
    });

    expect(store.getState().messages.at(-1)?.content).toBe(
      "先收窄目标用户，再讨论 MVP。",
    );
    expect(store.getState().messages.at(-1)?.role).toBe("assistant");
  });

  it("hydrates a recovered session as a consistent fresh snapshot", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("旧输入");
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        delta: "旧回答",
      },
    });

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "新 idea",
      },
      state: {
        idea: "新 idea",
        stage_hint: "验证需求",
      },
      prd_snapshot: {
        sections: {
          target_user: {
            title: "目标用户",
            content: "新的目标用户",
            status: "confirmed",
          },
        },
      },
    });

    expect(store.getState().inputValue).toBe("新 idea");
    expect(store.getState().messages).toEqual([]);
    expect(store.getState().currentAction).toBeNull();
    expect(store.getState().isStreaming).toBe(false);
    expect(store.getState().pendingUserInput).toBeNull();
    expect(store.getState().prd.sections.target_user?.content).toBe("新的目标用户");
  });
});


describe("parseEventStream", () => {
  it("parses sse chunks into typed events", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: action.decided\ndata: {"action":"probe_deeper","target":"target_user","reason":"继续追问"}\n\n' +
              'event: assistant.delta\ndata: {"delta":"先收窄目标用户"}\n\n',
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
          reason: "继续追问",
        },
      },
      {
        type: "assistant.delta",
        data: {
          delta: "先收窄目标用户",
        },
      },
    ]);
  });
});
