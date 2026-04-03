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

    expect(await screen.findByRole("heading", { name: "创建新会话" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建并进入工作台" })).toBeInTheDocument();
  });

  it("redirects to the latest existing session", async () => {
    listSessionsMock.mockResolvedValue({
      sessions: [
        {
          id: "session-1",
          user_id: "user-1",
          title: "最近活跃会话",
          initial_idea: "most recent activity",
        },
        {
          id: "session-2",
          user_id: "user-1",
          title: "更早的会话",
          initial_idea: "older idea",
        },
      ],
    });

    render(<WorkspacePage />);

    await screen.findByText("最近活跃");
    expect(pushMock).toHaveBeenCalledWith("/workspace/session-1");
  });
});
