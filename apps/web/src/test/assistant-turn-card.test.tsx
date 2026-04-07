import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssistantTurnCard } from "../components/workspace/assistant-turn-card";
import { workspaceStore } from "../store/workspace-store";
import type { DecisionGuidance } from "../lib/types";

describe("AssistantTurnCard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    workspaceStore.setState((state) => ({ ...state, inputValue: "" }));
  });

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

    expect(screen.getByRole("button", { name: "生成中..." })).toBeDisabled();
  });

  it("shows version history entry and opens dialog with latest highlighted", () => {
    render(
      <AssistantTurnCard
        canRegenerate
        currentAction={null}
        latestAssistantMessage="第二版回复"
        replyVersions={[
          {
            assistantVersionId: "v1",
            content: "第一版回复",
            isLatest: false,
            versionNo: 1,
          },
          {
            assistantVersionId: "v2",
            content: "第二版回复",
            isLatest: true,
            versionNo: 2,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "重新生成历史" }));

    const dialog = screen.getByRole("dialog", { name: "重新生成历史" });

    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "查看版本 2" })).toBeInTheDocument();
    expect(within(dialog).getAllByText("当前版本")).toHaveLength(2);
    expect(within(dialog).getByRole("button", { name: "查看版本 1" })).toBeInTheDocument();
    expect(within(dialog).getByText("第二版回复")).toBeInTheDocument();
  });

  it("renders decision guidance with stage label, reason, and recommendation buttons", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "choose",
      strategyLabel: "推动取舍",
      strategyReason: "目标用户过泛，先确定主线取舍。",
      nextBestQuestions: [
        "你愿意先收敛用户还是首个场景？",
        "最佳主线是聚焦哪个核心问题？",
      ],
    };

    render(
      <AssistantTurnCard
        currentAction={null}
        decisionGuidance={guidance}
        latestAssistantMessage="我先帮你收敛 MVP 的首个关键场景。"
      />,
    );

    expect(screen.getByText("下一步建议")).toBeInTheDocument();
    expect(screen.getByText("推动取舍")).toBeInTheDocument();
    expect(screen.getByText("目标用户过泛，先确定主线取舍。"))
      .toBeInTheDocument();
    guidance.nextBestQuestions.forEach((question) => {
      expect(screen.getByRole("button", { name: question })).toBeInTheDocument();
    });
  });

  it("still shows stage label and buttons when strategy reason is missing", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "choose",
      strategyLabel: "推动取舍",
      strategyReason: null,
      nextBestQuestions: ["先确定主线再调整方案"],
    };

    render(
      <AssistantTurnCard
        currentAction={null}
        decisionGuidance={guidance}
        latestAssistantMessage="我先帮你收敛 MVP 的首个关键场景。"
      />,
    );

    expect(screen.getByText("推动取舍")).toBeInTheDocument();
    expect(screen.queryByText("我先帮你收敛 MVP 的首个关键场景。"))
      .toBeInTheDocument();
    expect(screen.queryByLabelText("decision-guidance-reason"))
      .not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "先确定主线再调整方案" }))
      .toBeInTheDocument();
  });

  it("populates the input when a recommendation is clicked", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "choose",
      strategyLabel: "推动取舍",
      strategyReason: "目标用户过泛，先确定主线取舍。",
      nextBestQuestions: ["你愿意先收敛用户还是首个场景？"],
    };
    const onSelect = vi.fn();

    render(
      <AssistantTurnCard
        currentAction={null}
        decisionGuidance={guidance}
        onSelectDecisionGuidanceQuestion={onSelect}
        latestAssistantMessage="我先帮你收敛 MVP 的首个关键场景。"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: guidance.nextBestQuestions[0] }));

    expect(onSelect).toHaveBeenCalledWith("你愿意先收敛用户还是首个场景？");
  });

  it("does not render guidance when no decision guidance is provided", () => {
    render(
      <AssistantTurnCard
        currentAction={null}
        latestAssistantMessage="我先帮你收敛 MVP 的首个关键场景。"
      />,
    );

    expect(screen.queryByText("下一步建议")).not.toBeInTheDocument();
  });
});
