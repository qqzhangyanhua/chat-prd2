import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssistantTurnCard } from "../components/workspace/assistant-turn-card";

describe("AssistantTurnCard", () => {
  it("shows an interrupted marker when the latest round was manually stopped", () => {
    render(
      <AssistantTurnCard
        currentAction={null}
        latestAssistantMessage="我先帮你收敛 MVP 的首个关键场景。"
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
        latestAssistantMessage="我先帮你收敛 MVP 的首个关键场景。"
        onRegenerate={onRegenerate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "重新生成" }));

    expect(onRegenerate).toHaveBeenCalledTimes(1);
  });

  it("shows loading text and disabled state while regenerating", () => {
    render(
      <AssistantTurnCard
        canRegenerate
        currentAction={null}
        isRegenerating
        latestAssistantMessage="我先帮你收敛 MVP 的首个关键场景。"
      />,
    );

    expect(screen.getByRole("button", { name: "重新生成中..." })).toBeDisabled();
  });
});
