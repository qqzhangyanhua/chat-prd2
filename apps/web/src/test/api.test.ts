import { beforeEach, describe, expect, it, vi } from "vitest";

import { listSessions } from "../lib/api";
import { useAuthStore } from "../store/auth-store";

describe("api auth handling", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    useAuthStore.getState().clearAuth();
    useAuthStore.getState().setAuth({
      accessToken: "expired-token",
      user: {
        id: "user-1",
        email: "user@example.com",
        is_admin: false,
      },
    });
  });

  it("clears auth state and redirects to /login when a protected request returns 401", async () => {
    const assignMock = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "未认证" }), {
          status: 401,
          headers: {
            "Content-Type": "application/json",
          },
        }),
      ),
    );
    vi.stubGlobal("location", {
      assign: assignMock,
    });

    await expect(listSessions("expired-token")).rejects.toThrow("未认证");

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(assignMock).toHaveBeenCalledWith("/login");
  });
});
