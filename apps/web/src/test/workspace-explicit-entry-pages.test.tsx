import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import WorkspaceHomePage from "../app/workspace/home/page";
import WorkspaceNewPage from "../app/workspace/new/page";

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

vi.mock("../hooks/use-auth-guard", () => ({
  useAuthGuard: vi.fn(() => ({ hydrated: true })),
}));

describe("Workspace explicit entry pages", () => {
  it("renders workspace home page without auto redirecting to latest session", async () => {
    listSessionsMock.mockResolvedValue({
      sessions: [
        {
          id: "session-1",
          user_id: "user-1",
          title: "最近活跃会话",
          initial_idea: "most recent activity",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
        },
      ],
    });
    pushMock.mockReset();

    render(<WorkspaceHomePage />);

    expect(await screen.findByText("Describe your idea")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders workspace new page without auto redirecting to latest session", async () => {
    listSessionsMock.mockResolvedValue({
      sessions: [
        {
          id: "session-1",
          user_id: "user-1",
          title: "最近活跃会话",
          initial_idea: "most recent activity",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
        },
      ],
    });
    pushMock.mockReset();

    render(<WorkspaceNewPage />);

    expect(await screen.findByText("Describe your idea")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
