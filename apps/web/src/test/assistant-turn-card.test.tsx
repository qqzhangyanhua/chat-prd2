import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AssistantTurnCard } from "../components/workspace/assistant-turn-card";

describe("AssistantTurnCard", () => {
  it("shows an interrupted marker when the latest round was manually stopped", () => {
    render(
      <AssistantTurnCard
        currentAction={null}
        latestAssistantMessage="先讲讲他们在定义 MVP 时最常卡住的地方。"
        showInterruptedMarker
      />,
    );

    expect(screen.getByText("本轮已手动中断")).toBeInTheDocument();
  });
});
