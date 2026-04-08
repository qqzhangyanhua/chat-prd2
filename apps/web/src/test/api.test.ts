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
        new Response(JSON.stringify({
          detail: "未认证",
          error: {
            code: "AUTH_REQUIRED",
            message: "未认证",
            recovery_action: {
              type: "login",
              label: "重新登录",
              target: "/login",
            },
          },
        }), {
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

    await expect(listSessions("expired-token")).rejects.toMatchObject({
      code: "AUTH_REQUIRED",
      message: "未认证",
      recoveryAction: {
        type: "login",
        label: "重新登录",
        target: "/login",
      },
    });

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(assignMock).toHaveBeenCalledWith("/login");
  });
});
