import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HomeAuthRedirect } from "../components/home/home-auth-redirect";

const getHealthStatusMock = vi.fn();
const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

vi.mock("../lib/api", () => ({
  getHealthStatus: (...args: unknown[]) => getHealthStatusMock(...args),
  SCHEMA_OUTDATED_DETAIL: "数据库结构版本过旧，请先执行 alembic upgrade head",
}));

vi.mock("../store/auth-store", () => ({
  useAuthStore: vi.fn(),
}));

import { useAuthStore } from "../store/auth-store";

describe("HomeAuthRedirect", () => {
  beforeEach(() => {
    getHealthStatusMock.mockReset();
    replaceMock.mockReset();
  });

  it("does nothing when the visitor is not authenticated", () => {
    vi.mocked(useAuthStore).mockImplementation((selector) =>
      selector({ isAuthenticated: false } as never),
    );

    render(<HomeAuthRedirect />);

    expect(getHealthStatusMock).not.toHaveBeenCalled();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("redirects authenticated users to workspace when schema is ready", async () => {
    vi.mocked(useAuthStore).mockImplementation((selector) =>
      selector({ isAuthenticated: true } as never),
    );
    getHealthStatusMock.mockResolvedValue({
      status: "ok",
      schema: "ready",
    });

    render(<HomeAuthRedirect />);

    await waitFor(() => {
      expect(getHealthStatusMock).toHaveBeenCalledTimes(1);
      expect(replaceMock).toHaveBeenCalledWith("/workspace");
    });
  });

  it("shows a migration notice instead of redirecting when schema is outdated", async () => {
    vi.mocked(useAuthStore).mockImplementation((selector) =>
      selector({ isAuthenticated: true } as never),
    );
    getHealthStatusMock.mockResolvedValue({
      status: "degraded",
      schema: "outdated",
      detail: "数据库结构版本过旧，请先执行 alembic upgrade head",
      missing_tables: ["agent_turn_decisions"],
    });

    render(<HomeAuthRedirect />);

    expect(await screen.findByText("后端数据库迁移未完成")).toBeInTheDocument();
    expect(screen.getByText("agent_turn_decisions")).toBeInTheDocument();
    expect(screen.getByText(/cd apps\/api && alembic upgrade head/i)).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("still redirects when health probing fails unexpectedly", async () => {
    vi.mocked(useAuthStore).mockImplementation((selector) =>
      selector({ isAuthenticated: true } as never),
    );
    getHealthStatusMock.mockRejectedValue(new Error("健康检查失败"));

    render(<HomeAuthRedirect />);

    await waitFor(() => {
      expect(getHealthStatusMock).toHaveBeenCalledTimes(1);
      expect(replaceMock).toHaveBeenCalledWith("/workspace");
    });

    expect(screen.queryByText("后端数据库迁移未完成")).not.toBeInTheDocument();
  });
});
