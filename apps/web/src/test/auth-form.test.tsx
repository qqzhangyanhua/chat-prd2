import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthForm } from "../components/auth/auth-form";
import { useAuthStore } from "../store/auth-store";


const pushMock = vi.fn();
const loginMock = vi.fn();
const registerMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("../lib/api", () => ({
  login: (...args: unknown[]) => loginMock(...args),
  register: (...args: unknown[]) => registerMock(...args),
}));


describe("AuthForm", () => {
  beforeEach(() => {
    pushMock.mockReset();
    loginMock.mockReset();
    registerMock.mockReset();
    useAuthStore.getState().clearAuth();
    window.localStorage.clear();
  });

  it("renders email and password inputs", () => {
    render(<AuthForm mode="login" />);

    expect(screen.getByLabelText("邮箱")).toBeInTheDocument();
    expect(screen.getByLabelText("密码")).toBeInTheDocument();
  });

  it("persists auth state and redirects after login succeeds", async () => {
    loginMock.mockResolvedValue({
      user: { id: "user-1", email: "user@example.com" },
      access_token: "token-123",
    });

    render(<AuthForm mode="login" />);

    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("密码"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith("user@example.com", "secret123");
      expect(useAuthStore.getState().accessToken).toBe("token-123");
      expect(useAuthStore.getState().user?.email).toBe("user@example.com");
      expect(pushMock).toHaveBeenCalledWith("/workspace");
    });
  });

  it("submits register request in register mode", async () => {
    registerMock.mockResolvedValue({
      user: { id: "user-2", email: "new@example.com" },
      access_token: "token-456",
    });

    render(<AuthForm mode="register" />);

    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("密码"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "注册" }));

    await waitFor(() => {
      expect(registerMock).toHaveBeenCalledWith("new@example.com", "secret123");
      expect(useAuthStore.getState().accessToken).toBe("token-456");
      expect(pushMock).toHaveBeenCalledWith("/workspace");
    });
  });
});
