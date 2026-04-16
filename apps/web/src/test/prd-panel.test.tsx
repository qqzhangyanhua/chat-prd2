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
        ...workspaceStore.getState().prd,
        sections: {
          ...workspaceStore.getState().prd.sections,
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
        sectionsChanged: [],
        missingSections: [],
        gapPrompts: [],
        readyForConfirmation: false,
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
    expect(screen.getByText("首版优先浏览器端，不做桌面插件。")).toBeInTheDocument();
    expect(screen.getByText("是否需要外链分享与到期控制？")).toBeInTheDocument();
    expect(screen.getByText("当前已满足终稿整理条件，你可以直接生成最终版 PRD。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成最终版 PRD" })).toBeInTheDocument();
  });

  it("orders finalized extra sections before open questions", () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      prd: {
        ...workspaceStore.getState().prd,
        sections: {
          ...workspaceStore.getState().prd.sections,
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
        sectionsChanged: [],
        missingSections: [],
        gapPrompts: [],
        readyForConfirmation: false,
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
    expect(screen.getByText("当前已经进入稳定终稿视图，后续补充会基于终稿继续增量更新。")).toBeInTheDocument();
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
    expect(screen.getByText("首版只支持浏览器端，不做桌面插件。")).toBeInTheDocument();
    expect(screen.getByText("7 天内至少完成 10 次有效预览。")).toBeInTheDocument();
  });

  it("does not render first draft content from draft.updated events", () => {
    render(<PrdPanel sessionId="demo-session" />);

    act(() => {
      workspaceStore.getState().applyEvent({
        type: "draft.updated",
        data: {
          sections: {
            target_user: {
              title: "目标用户",
              completeness: "partial",
              entries: [
                {
                  id: "entry-target-user-1",
                  text: "第一版先服务独立开发者。",
                  assertion_state: "confirmed",
                  evidence_ref_ids: ["evidence-user-1"],
                },
              ],
            },
          },
          evidence_registry: [
            {
              id: "evidence-user-1",
              kind: "user_message",
              excerpt: "我想先服务独立开发者。",
              section_keys: ["target_user"],
            },
          ],
          draft_summary: {
            section_keys: ["target_user"],
            entry_ids: ["entry-target-user-1"],
            evidence_ids: ["evidence-user-1"],
          },
          sections_changed: ["target_user"],
          entry_ids: ["entry-target-user-1"],
        },
      });
    });

    expect(screen.queryByText("第一版先服务独立开发者。")).not.toBeInTheDocument();
  });

  it("renders changed section highlight and gap prompts from phase4 contract", () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      prd: {
        ...workspaceStore.getState().prd,
        sections: {
          ...workspaceStore.getState().prd.sections,
          target_user: {
            title: "目标用户",
            content: "独立开发者",
            status: "confirmed",
          },
          problem: {
            title: "核心问题",
            content: "需求确认成本高",
            status: "inferred",
          },
        },
        sectionsChanged: ["problem"],
        missingSections: ["solution"],
        gapPrompts: ["请补充「solution」内容"],
        readyForConfirmation: false,
        meta: {
          stageLabel: "草稿中",
          stageTone: "draft",
          criticSummary: "还有缺口待补齐。",
          criticGaps: [],
          draftVersion: 3,
          nextQuestion: null,
        },
      },
    });

    render(<PrdPanel sessionId="demo-session" />);

    expect(screen.getByText("本轮更新")).toBeInTheDocument();
    expect(screen.getByText("继续补这 1 项")).toBeInTheDocument();
    expect(screen.getByText("请补充「solution」内容")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认初稿并生成最终版 PRD" })).not.toBeInTheDocument();
  });

  it("renders review summary without polluting prd sections", () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      prdReview: {
        verdict: "revise",
        status: "drafting",
        summary: "当前 PRD 结构已成型，但仍需补齐边界。",
        checks: {},
        gaps: ["请补充范围边界"],
        missing_sections: ["constraints"],
        ready_for_confirmation: false,
      },
      prd: {
        ...workspaceStore.getState().prd,
        sections: {
          ...workspaceStore.getState().prd.sections,
          solution: {
            title: "解决方案",
            content: "通过 replay timeline 回看收敛过程。",
            status: "confirmed",
          },
        },
      },
    });

    render(<PrdPanel sessionId="demo-session" />);

    expect(screen.getByTestId("prd-review-summary")).toBeInTheDocument();
    expect(screen.getByText("当前 PRD 结构已成型，但仍需补齐边界。")).toBeInTheDocument();
    expect(screen.getByText("请补充范围边界")).toBeInTheDocument();
    expect(screen.getByText("通过 replay timeline 回看收敛过程。")).toBeInTheDocument();
    expect(screen.queryByText("scope_boundary")).not.toBeInTheDocument();
  });

  it("renders confirm cta when prd panel is ready for confirmation", () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      isFinalizeReady: true,
      isCompleted: false,
      prd: {
        ...workspaceStore.getState().prd,
        sectionsChanged: ["solution"],
        missingSections: [],
        gapPrompts: [],
        readyForConfirmation: true,
        meta: {
          stageLabel: "可确认初稿",
          stageTone: "ready",
          criticSummary: "关键信息已基本齐备，可以给用户确认当前 PRD 初稿。",
          criticGaps: [],
          draftVersion: 4,
          nextQuestion: null,
        },
      },
    });

    render(<PrdPanel sessionId="demo-session" />);

    expect(screen.getByText("可以先确认当前 PRD 初稿，再生成最终版。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认初稿并生成最终版 PRD" })).toBeInTheDocument();
  });
});
