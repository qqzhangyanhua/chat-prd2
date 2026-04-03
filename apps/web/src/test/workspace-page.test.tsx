import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WorkspacePage from "../app/workspace/page";


const listSessionsMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual("../lib/api");
  return {
    ...actual,
    listSessions: (...args: unknown[]) => listSessionsMock(...args),
  };
});


describe("WorkspacePage", () => {
  beforeEach(() => {
    listSessionsMock.mockReset();
    pushMock.mockReset();
    listSessionsMock.mockResolvedValue({ sessions: [] });
  });

  it("renders the session entry surface", async () => {
    render(<WorkspacePage />);

    expect(await screen.findByRole("heading", { name: "开始一个新会话" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建并进入工作台" })).toBeInTheDocument();
  });

  it("shows existing sessions from api", async () => {
    listSessionsMock.mockResolvedValue({
      sessions: [
        {
          id: "session-1",
          user_id: "user-1",
          title: "已有项目",
          initial_idea: "idea",
        },
      ],
    });

    render(<WorkspacePage />);

    expect(await screen.findByRole("button", { name: "进入已有项目" })).toBeInTheDocument();
    expect(screen.getByText("已有项目")).toBeInTheDocument();
  });
});
