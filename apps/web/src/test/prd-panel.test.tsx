import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { PrdPanel } from "../components/workspace/prd-panel";
import { workspaceStore } from "../store/workspace-store";

describe("PrdPanel", () => {
  beforeEach(() => {
    workspaceStore.setState(workspaceStore.getInitialState(), true);
  });

  it("renders prd stage and critic summary from store meta", () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      isFinalizeReady: true,
      isCompleted: false,
      prd: {
        extraSections: {
          constraints: {
            title: "约束条件",
            content: "首版优先浏览器端，不做桌面插件。",
            status: "confirmed",
          },
          open_questions: {
            title: "待确认问题",
            content: "是否需要外链分享与到期控制？",
            status: "inferred",
          },
        },
        sections: workspaceStore.getState().prd.sections,
        meta: {
          stageLabel: "可整理终稿",
          stageTone: "ready",
          criticSummary: "Critic 已通过，可以整理最终版 PRD。",
          criticGaps: ["缺少成功指标", "缺少不做清单"],
          draftVersion: 3,
          nextQuestion: "如果你确认无误，我可以开始整理最终版 PRD。你希望最终版更偏业务描述还是更偏技术实现细节？",
        },
      },
    });

    render(<PrdPanel sessionId="demo-session" />);

    expect(screen.getByText("可整理终稿")).toBeInTheDocument();
    expect(screen.getByText("Critic 已通过，可以整理最终版 PRD。")).toBeInTheDocument();
    expect(screen.getByText("PRD v3")).toBeInTheDocument();
    expect(screen.getByText("缺少成功指标")).toBeInTheDocument();
    expect(screen.getByText("缺少不做清单")).toBeInTheDocument();
    expect(
      screen.getByText("如果你确认无误，我可以开始整理最终版 PRD。你希望最终版更偏业务描述还是更偏技术实现细节？"),
    ).toBeInTheDocument();
    expect(screen.getByText("草稿补充")).toBeInTheDocument();
    expect(screen.getByText("首版优先浏览器端，不做桌面插件。")).toBeInTheDocument();
    expect(screen.getByText("是否需要外链分享与到期控制？")).toBeInTheDocument();
    expect(screen.getByText("当前已满足终稿整理条件，你可以直接生成最终版 PRD。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成最终版 PRD" })).toBeInTheDocument();
  });

  it("orders finalized extra sections before open questions", () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      prd: {
        sections: workspaceStore.getState().prd.sections,
        extraSections: {
          open_questions: {
            title: "待确认问题",
            content: "是否需要审批流？",
            status: "inferred",
          },
          success_metrics: {
            title: "成功指标",
            content: "7 天内完成 10 次有效预览。",
            status: "confirmed",
          },
          constraints: {
            title: "约束条件",
            content: "首版只支持浏览器端。",
            status: "confirmed",
          },
        },
        meta: {
          stageLabel: "已生成终稿",
          stageTone: "final",
          criticSummary: "当前会话已经整理出最终版 PRD，后续修改会基于终稿增量更新。",
          criticGaps: [],
          draftVersion: 4,
          nextQuestion: null,
        },
      },
    });

    render(<PrdPanel sessionId="demo-session" />);

    const cards = screen.getAllByRole("article");
    const titles = cards.map((card) => card.querySelector("h3")?.textContent ?? "");

    expect(titles.indexOf("约束条件")).toBeLessThan(titles.indexOf("待确认问题"));
    expect(titles.indexOf("成功指标")).toBeLessThan(titles.indexOf("待确认问题"));
    expect(screen.getByText("已生成最终版 PRD，后续补充会基于终稿继续迭代。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "生成最终版 PRD" })).not.toBeInTheDocument();
  });

  it("renders extra draft sections pushed by prd.updated events", () => {
    render(<PrdPanel sessionId="demo-session" />);

    act(() => {
      workspaceStore.getState().applyEvent({
        type: "prd.updated",
        data: {
          sections: {
            solution: {
              title: "解决方案",
              content: "先做浏览器内预览、评论和分享闭环。",
              status: "inferred",
            },
            constraints: {
              title: "约束条件",
              content: "首版只支持浏览器端，不做桌面插件。",
              status: "confirmed",
            },
            success_metrics: {
              title: "成功指标",
              content: "7 天内至少完成 10 次有效预览。",
              status: "inferred",
            },
          },
        },
      });
    });

    expect(screen.getByText("先做浏览器内预览、评论和分享闭环。")).toBeInTheDocument();
    expect(screen.getByText("草稿补充")).toBeInTheDocument();
    expect(screen.getByText("首版只支持浏览器端，不做桌面插件。")).toBeInTheDocument();
    expect(screen.getByText("7 天内至少完成 10 次有效预览。")).toBeInTheDocument();
  });
});
