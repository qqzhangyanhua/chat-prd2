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

  it("shows finalize button when finalize action is available", () => {
    const onFinalize = vi.fn();

    render(
      <AssistantTurnCard
        currentAction={null}
        latestAssistantMessage="当前信息已齐备，可生成最终版。"
        onFinalize={onFinalize}
        showFinalizeAction
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "生成最终版 PRD" }));

    expect(onFinalize).toHaveBeenCalledTimes(1);
  });

  it("shows completed reminder inside the assistant card", () => {
    render(
      <AssistantTurnCard
        completedHint="已生成最终版，继续输入会重新打开编辑流程。"
        currentAction={null}
        latestAssistantMessage="这是当前最终版摘要。"
      />,
    );

    expect(screen.getByText("已生成最终版，继续输入会重新打开编辑流程。")).toBeInTheDocument();
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
      confirmQuickReplies: [],
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

  it("renders structured suggestion options before question chips", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "greet",
      strategyLabel: "欢迎引导",
      strategyReason: "先给用户几个容易选择的方向。",
      nextBestQuestions: [],
      confirmQuickReplies: [],
      suggestionOptions: [
        {
          label: "讨论产品想法",
          content: "我有一个产品想法，想和你一起梳理成清晰的 PRD。",
          rationale: "适合已经有方向、想快速进入产品讨论的情况。",
          priority: 1,
          type: "direction",
        },
      ],
    };

    render(
      <AssistantTurnCard
        currentAction={null}
        decisionGuidance={guidance}
        latestAssistantMessage="先选一个最接近你的方向。"
      />,
    );

    expect(screen.getByText("可直接选择一个方向")).toBeInTheDocument();
    expect(screen.getByText("讨论产品想法")).toBeInTheDocument();
    expect(screen.getByText("我有一个产品想法，想和你一起梳理成清晰的 PRD。")).toBeInTheDocument();
  });

  it("renders fixed A/B/C/D guidance options together with a free supplement entry", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "greet",
      strategyLabel: "欢迎引导",
      strategyReason: "先给用户四个最接近当前上下文的方向。",
      nextBestQuestions: [],
      confirmQuickReplies: [],
      suggestionOptions: [
        {
          label: "先聊目标用户",
          content: "我想先把目标用户讲清楚，再继续往下拆。",
          rationale: "先定用户，后续问题和方案更容易收敛。",
          priority: 1,
          type: "direction",
        },
        {
          label: "先聊使用场景",
          content: "我想先把用户会在哪个场景下使用这款产品讲清楚。",
          rationale: "先锁定场景，便于判断需求强度。",
          priority: 2,
          type: "direction",
        },
        {
          label: "先聊核心痛点",
          content: "我想先确认用户最痛的那个问题到底是什么。",
          rationale: "先抓痛点，再看功能是否成立。",
          priority: 3,
          type: "direction",
        },
        {
          label: "先聊验证方式",
          content: "我想先聊第一轮要怎么验证这个想法值不值得做。",
          rationale: "优先明确验证动作，降低空想风险。",
          priority: 4,
          type: "direction",
        },
      ],
    };

    render(
      <AssistantTurnCard
        currentAction={null}
        decisionGuidance={guidance}
        latestAssistantMessage="先选一个最接近你的方向。"
      />,
    );

    expect(screen.getByText("方案 A")).toBeInTheDocument();
    expect(screen.getByText("方案 B")).toBeInTheDocument();
    expect(screen.getByText("方案 C")).toBeInTheDocument();
    expect(screen.getByText("方案 D")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /自由补充/i })).toBeInTheDocument();
  });

  it("uses suggestion option content for the selection callback", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "greet",
      strategyLabel: "欢迎引导",
      strategyReason: "先给用户几个容易选择的方向。",
      nextBestQuestions: [],
      confirmQuickReplies: [],
      suggestionOptions: [
        {
          label: "从模糊方向开始",
          content: "我现在只有一个模糊方向，还不知道怎么描述，想让你带着我一步步梳理。",
          rationale: "适合还在很早期、需要 AI 先给框架的情况。",
          priority: 1,
          type: "direction",
        },
      ],
    };
    const onSelect = vi.fn();

    render(
      <AssistantTurnCard
        currentAction={null}
        decisionGuidance={guidance}
        onSelectDecisionGuidanceQuestion={onSelect}
        latestAssistantMessage="先选一个最接近你的方向。"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /从模糊方向开始/i }));

    expect(onSelect).toHaveBeenCalledWith("我现在只有一个模糊方向，还不知道怎么描述，想让你带着我一步步梳理。");
  });

  it("uses a dedicated callback for free supplement instead of the suggestion selection callback", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "greet",
      strategyLabel: "欢迎引导",
      strategyReason: "先给用户几个容易选择的方向。",
      nextBestQuestions: [],
      confirmQuickReplies: [],
      suggestionOptions: [
        {
          label: "先聊目标用户",
          content: "我想先把目标用户讲清楚，再继续往下拆。",
          rationale: "先定用户，后续问题和方案更容易收敛。",
          priority: 1,
          type: "direction",
        },
        {
          label: "先聊使用场景",
          content: "我想先把用户会在哪个场景下使用这款产品讲清楚。",
          rationale: "先锁定场景，便于判断需求强度。",
          priority: 2,
          type: "direction",
        },
        {
          label: "先聊核心痛点",
          content: "我想先确认用户最痛的那个问题到底是什么。",
          rationale: "先抓痛点，再看功能是否成立。",
          priority: 3,
          type: "direction",
        },
        {
          label: "先聊验证方式",
          content: "我想先聊第一轮要怎么验证这个想法值不值得做。",
          rationale: "优先明确验证动作，降低空想风险。",
          priority: 4,
          type: "direction",
        },
      ],
    };
    const onSelect = vi.fn();
    const onRequestFreeSupplement = vi.fn();

    render(
      <AssistantTurnCard
        {...({
          currentAction: null,
          decisionGuidance: guidance,
          latestAssistantMessage: "先选一个最接近你的方向。",
          onRequestFreeSupplement,
          onSelectDecisionGuidanceQuestion: onSelect,
        } as any)}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /自由补充/i }));

    expect(onRequestFreeSupplement).toHaveBeenCalledTimes(1);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("shows collaboration mode label when provided", () => {
    render(
      <AssistantTurnCard
        collaborationModeLabel="深度推演模式"
        currentAction={null}
        latestAssistantMessage="我先帮你拆开复杂约束，再逐步收敛方案。"
      />,
    );

    expect(screen.getByText("当前协作模式")).toBeInTheDocument();
    expect(screen.getByText("深度推演模式")).toBeInTheDocument();
  });

  it("still shows stage label and buttons when strategy reason is missing", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "choose",
      strategyLabel: "推动取舍",
      strategyReason: null,
      nextBestQuestions: ["先确定主线再调整方案"],
      confirmQuickReplies: [],
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
      confirmQuickReplies: [],
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

  it("shows stable confirmation quick replies during confirm stage", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "confirm",
      strategyLabel: "确认共识",
      strategyReason: "核心信息已基本齐备，先锁定共识。",
      nextBestQuestions: ["请确认当前理解是否准确"],
      confirmQuickReplies: [
        "确认，继续下一步",
        "不对，先改目标用户",
        "不对，先改核心问题",
      ],
    };

    render(
      <AssistantTurnCard
        currentAction={null}
        decisionGuidance={guidance}
        latestAssistantMessage="我先把当前共识收口。"
      />,
    );

    expect(screen.getByText("确认后直接回复")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认，继续下一步" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "不对，先改目标用户" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "不对，先改核心问题" })).toBeInTheDocument();
  });

  it("uses the same selection callback for confirmation quick replies", () => {
    const guidance: DecisionGuidance = {
      conversationStrategy: "confirm",
      strategyLabel: "确认共识",
      strategyReason: "核心信息已基本齐备，先锁定共识。",
      nextBestQuestions: ["请确认当前理解是否准确"],
      confirmQuickReplies: [
        "确认，继续下一步",
        "不对，先改目标用户",
        "不对，先改核心问题",
      ],
    };
    const onSelect = vi.fn();

    render(
      <AssistantTurnCard
        currentAction={null}
        decisionGuidance={guidance}
        onSelectDecisionGuidanceQuestion={onSelect}
        latestAssistantMessage="我先把当前共识收口。"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "确认，继续下一步" }));

    expect(onSelect).toHaveBeenCalledWith("确认，继续下一步");
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
