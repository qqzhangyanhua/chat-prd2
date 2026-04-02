import { render, screen } from "@testing-library/react";

import WorkspacePage from "../app/workspace/page";


describe("WorkspacePage", () => {
  it("renders sidebar conversation and prd panel", () => {
    render(<WorkspacePage />);

    expect(screen.getByText("项目面板")).toBeInTheDocument();
    expect(screen.getByText("对话推进")).toBeInTheDocument();
    expect(screen.getByText("PRD")).toBeInTheDocument();
  });

  it("shows the structured workspace sections", () => {
    render(<WorkspacePage />);

    expect(screen.getByText("理解")).toBeInTheDocument();
    expect(screen.getByText("风险")).toBeInTheDocument();
    expect(screen.getByText("下一步问题")).toBeInTheDocument();
    expect(screen.getByText("目标用户")).toBeInTheDocument();
    expect(screen.getByText("MVP 范围")).toBeInTheDocument();
  });

  it("keeps the composer button non-submitting in the static shell", () => {
    render(<WorkspacePage />);

    expect(screen.getByRole("button", { name: "继续推进" })).toHaveAttribute(
      "type",
      "button",
    );
  });
});
