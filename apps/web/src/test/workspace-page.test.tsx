import { render, screen, waitFor } from "@testing-library/react";
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

  it("renders the current session entry surface", async () => {
    render(<WorkspacePage />);

    expect(await screen.findByText("Describe your idea")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start Session" })).toBeInTheDocument();
  });

  it("redirects to the latest existing session", async () => {
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
        {
          id: "session-2",
          user_id: "user-1",
          title: "更早的会话",
          initial_idea: "older idea",
          created_at: "2026-04-04T00:00:00Z",
          updated_at: "2026-04-04T00:00:00Z",
        },
      ],
    });

    render(<WorkspacePage />);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/workspace/session-1");
    });
  });
});
