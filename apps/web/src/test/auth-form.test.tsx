import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthForm } from "../components/auth/auth-form";
import { useAuthStore } from "../store/auth-store";

const pushMock = vi.fn();
const getHealthStatusMock = vi.fn();
const loginMock = vi.fn();
const registerMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", () => ({
  getHealthStatus: (...args: unknown[]) => getHealthStatusMock(...args),
  login: (...args: unknown[]) => loginMock(...args),
  register: (...args: unknown[]) => registerMock(...args),
  SCHEMA_OUTDATED_DETAIL: "数据库结构版本过旧，请先执行 alembic upgrade head",
}));

describe("AuthForm", () => {
  beforeEach(() => {
    pushMock.mockReset();
    getHealthStatusMock.mockReset();
    loginMock.mockReset();
    registerMock.mockReset();
    useAuthStore.getState().clearAuth();
    window.localStorage.clear();
  });

  it("renders the current email and password inputs", () => {
    render(<AuthForm mode="login" />);

    expect(screen.getByPlaceholderText("Business email*")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password*")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeInTheDocument();
  });

  it("persists auth state and redirects after login succeeds", async () => {
    loginMock.mockResolvedValue({
      user: { id: "user-1", email: "user@example.com", is_admin: true },
      access_token: "token-123",
    });
    getHealthStatusMock.mockResolvedValue({
      status: "ok",
      schema: "ready",
    });

    render(<AuthForm mode="login" />);

    fireEvent.change(screen.getByPlaceholderText("Business email*"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password*"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith("user@example.com", "secret123");
      expect(getHealthStatusMock).toHaveBeenCalledTimes(1);
      expect(useAuthStore.getState().accessToken).toBe("token-123");
      expect(useAuthStore.getState().user?.email).toBe("user@example.com");
      expect(useAuthStore.getState().user?.is_admin).toBe(true);
      expect(pushMock).toHaveBeenCalledWith("/workspace");
    });
  });

  it("shows an explicit migration hint instead of redirecting when schema is outdated after login", async () => {
    loginMock.mockResolvedValue({
      user: { id: "user-1", email: "user@example.com", is_admin: false },
      access_token: "token-123",
    });
    getHealthStatusMock.mockResolvedValue({
      status: "degraded",
      schema: "outdated",
      detail: "数据库结构版本过旧，请先执行 alembic upgrade head",
      missing_tables: ["agent_turn_decisions"],
    });

    render(<AuthForm mode="login" />);

    fireEvent.change(screen.getByPlaceholderText("Business email*"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password*"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByText("后端数据库迁移未完成")).toBeInTheDocument();
    expect(screen.getByText("agent_turn_decisions")).toBeInTheDocument();
    expect(screen.getByText(/cd apps\/api && alembic upgrade head/i)).toBeInTheDocument();
    expect(useAuthStore.getState().accessToken).toBe("token-123");
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("still redirects after login when health probing fails unexpectedly", async () => {
    loginMock.mockResolvedValue({
      user: { id: "user-1", email: "user@example.com", is_admin: false },
      access_token: "token-123",
    });
    getHealthStatusMock.mockRejectedValue(new Error("健康检查失败"));

    render(<AuthForm mode="login" />);

    fireEvent.change(screen.getByPlaceholderText("Business email*"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password*"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => {
      expect(getHealthStatusMock).toHaveBeenCalledTimes(1);
      expect(pushMock).toHaveBeenCalledWith("/workspace");
    });

    expect(screen.queryByText("后端数据库迁移未完成")).not.toBeInTheDocument();
  });

  it("defaults is_admin to false when auth payload omits the field", async () => {
    loginMock.mockResolvedValue({
      user: { id: "user-1", email: "user@example.com" },
      access_token: "token-789",
    });
    getHealthStatusMock.mockResolvedValue({
      status: "ok",
      schema: "ready",
    });

    render(<AuthForm mode="login" />);

    fireEvent.change(screen.getByPlaceholderText("Business email*"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password*"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => {
      expect(useAuthStore.getState().accessToken).toBe("token-789");
      expect(useAuthStore.getState().user?.is_admin).toBe(false);
    });
  });

  it("submits register request in register mode", async () => {
    registerMock.mockResolvedValue({
      user: { id: "user-2", email: "new@example.com", is_admin: false },
      access_token: "token-456",
    });
    getHealthStatusMock.mockResolvedValue({
      status: "ok",
      schema: "ready",
    });

    render(<AuthForm mode="register" />);

    fireEvent.change(screen.getByPlaceholderText("Business email*"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password*"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => {
      expect(registerMock).toHaveBeenCalledWith("new@example.com", "secret123");
      expect(getHealthStatusMock).toHaveBeenCalledTimes(1);
      expect(useAuthStore.getState().accessToken).toBe("token-456");
      expect(pushMock).toHaveBeenCalledWith("/workspace");
    });
  });
});
