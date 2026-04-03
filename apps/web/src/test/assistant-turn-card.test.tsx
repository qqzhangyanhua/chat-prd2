import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

  it("shows a regenerate button when a previous input can be replayed", () => {
    const onRegenerate = vi.fn();

    render(
      <AssistantTurnCard
        canRegenerate
        currentAction={null}
        latestAssistantMessage="先讲讲他们在定义 MVP 时最常卡住的地方。"
        onRegenerate={onRegenerate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "重新生成" }));

    expect(onRegenerate).toHaveBeenCalledTimes(1);
  });
});
