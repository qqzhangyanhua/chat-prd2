import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthGuard } from "../hooks/use-auth-guard";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("../store/auth-store", () => ({
  useAuthStore: vi.fn(),
  useAuthHydrated: vi.fn(() => true),
}));

import { useAuthStore } from "../store/auth-store";

describe("useAuthGuard", () => {
  beforeEach(() => {
    pushMock.mockReset();
  });

  it("redirects to /login when not authenticated", () => {
    vi.mocked(useAuthStore).mockImplementation((selector) =>
      selector({ isAuthenticated: false } as never),
    );
    renderHook(() => useAuthGuard());
    expect(pushMock).toHaveBeenCalledWith("/login");
  });

  it("does not redirect when authenticated", () => {
    vi.mocked(useAuthStore).mockImplementation((selector) =>
      selector({ isAuthenticated: true } as never),
    );
    renderHook(() => useAuthGuard());
    expect(pushMock).not.toHaveBeenCalled();
  });
});
