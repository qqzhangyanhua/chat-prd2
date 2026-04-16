import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ReplayPanel } from "../components/workspace/replay-panel";
import { workspaceStore } from "../store/workspace-store";

describe("ReplayPanel", () => {
  beforeEach(() => {
    workspaceStore.setState(workspaceStore.getInitialState(), true);
  });

  it("renders replay timeline in snapshot order with finalize and export milestones", () => {
    workspaceStore.setState({
      ...workspaceStore.getState(),
      replayTimeline: [
        {
          id: "guidance-1",
          type: "guidance",
          title: "Guidance Decision",
          summary: "先让用户看到关键决策和变更。",
          sections_changed: [],
          metadata: {},
        },
        {
          id: "diagnostics-1",
          type: "diagnostics",
          title: "Diagnostics",
          summary: "用户是否真的需要回放",
          sections_changed: [],
          metadata: {},
        },
        {
          id: "prd-1",
          type: "prd_delta",
          title: "PRD Change",
          summary: "solution: 提供单会话 replay timeline。",
          sections_changed: ["mvp_scope", "solution"],
          metadata: {},
        },
        {
          id: "finalize-1",
          type: "finalize",
          title: "Finalize Milestone",
          summary: "会话已进入终稿交付状态。",
          sections_changed: [],
          metadata: {},
        },
        {
          id: "export-1",
          type: "export",
          title: "Export Milestone",
          summary: "终稿已具备导出为结构化 PRD 文本的条件。",
          sections_changed: [],
          metadata: { file_name: "ai-cofounder-prd.md" },
        },
      ],
    });

    render(<ReplayPanel />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
    expect(items[0]).toHaveTextContent("先让用户看到关键决策和变更。");
    expect(items[1]).toHaveTextContent("用户是否真的需要回放");
    expect(items[2]).toHaveTextContent("sections: mvp_scope, solution");
    expect(items[3]).toHaveTextContent("Finalize Milestone");
    expect(items[4]).toHaveTextContent("export: ai-cofounder-prd.md");
  });
});
