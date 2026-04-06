import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminModelsPage from "../app/admin/models/page";
import { useAuthStore } from "../store/auth-store";

const listAdminModelConfigsMock = vi.fn();
const createAdminModelConfigMock = vi.fn();
const updateAdminModelConfigMock = vi.fn();
const deleteAdminModelConfigMock = vi.fn();

vi.mock("../lib/api", () => ({
  listAdminModelConfigs: (...args: unknown[]) => listAdminModelConfigsMock(...args),
  createAdminModelConfig: (...args: unknown[]) => createAdminModelConfigMock(...args),
  updateAdminModelConfig: (...args: unknown[]) => updateAdminModelConfigMock(...args),
  deleteAdminModelConfig: (...args: unknown[]) => deleteAdminModelConfigMock(...args),
}));

describe("AdminModelsPage", () => {
  beforeEach(() => {
    listAdminModelConfigsMock.mockReset();
    createAdminModelConfigMock.mockReset();
    updateAdminModelConfigMock.mockReset();
    deleteAdminModelConfigMock.mockReset();

    useAuthStore.setState({
      accessToken: "token-1",
      isAuthenticated: true,
      user: {
        id: "admin-1",
        email: "admin@example.com",
        is_admin: true,
      },
    });

    listAdminModelConfigsMock.mockResolvedValue({
      items: [
        {
          id: "config-1",
          name: "OpenAI 主线路由",
          base_url: "https://api.openai.com/v1",
          api_key: "sk-live-1",
          model: "gpt-4.1",
          enabled: true,
          created_at: "2026-04-06T00:00:00Z",
          updated_at: "2026-04-06T00:00:00Z",
        },
      ],
    });
  });

  it("renders admin model management page for admins", async () => {
    render(<AdminModelsPage />);

    expect(await screen.findByText("模型管理")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建模型配置" })).toBeInTheDocument();

    await waitFor(() => {
      expect(listAdminModelConfigsMock).toHaveBeenCalledWith("token-1");
    });
    expect(screen.getByDisplayValue("OpenAI 主线路由")).toBeInTheDocument();
  });

  it("shows forbidden state for non-admin users", async () => {
    useAuthStore.setState({
      accessToken: "token-2",
      isAuthenticated: true,
      user: {
        id: "user-1",
        email: "user@example.com",
        is_admin: false,
      },
    });

    render(<AdminModelsPage />);

    expect(screen.getByText("仅管理员可访问模型管理页面。")).toBeInTheDocument();
    expect(listAdminModelConfigsMock).not.toHaveBeenCalled();
  });

  it("creates a model config with enabled flag", async () => {
    createAdminModelConfigMock.mockResolvedValue({
      id: "config-2",
      name: "Azure OpenAI",
      base_url: "https://azure.example.com/openai",
      api_key: "sk-azure",
      model: "gpt-4o-mini",
      enabled: true,
      created_at: "2026-04-06T01:00:00Z",
      updated_at: "2026-04-06T01:00:00Z",
    });

    render(<AdminModelsPage />);

    fireEvent.change(await screen.findByLabelText("新配置名称"), {
      target: { value: "Azure OpenAI" },
    });
    fireEvent.change(screen.getByLabelText("新 Base URL"), {
      target: { value: "https://azure.example.com/openai" },
    });
    fireEvent.change(screen.getByLabelText("新 API Key"), {
      target: { value: "sk-azure" },
    });
    fireEvent.change(screen.getByLabelText("新模型 ID"), {
      target: { value: "gpt-4o-mini" },
    });
    fireEvent.click(screen.getByLabelText("新配置启用"));
    fireEvent.click(screen.getByRole("button", { name: "创建模型配置" }));

    await waitFor(() => {
      expect(createAdminModelConfigMock).toHaveBeenCalledWith(
        {
          name: "Azure OpenAI",
          base_url: "https://azure.example.com/openai",
          api_key: "sk-azure",
          model: "gpt-4o-mini",
          enabled: true,
        },
        "token-1",
      );
    });

    expect(screen.getByDisplayValue("Azure OpenAI")).toBeInTheDocument();
  });

  it("edits an existing model config", async () => {
    updateAdminModelConfigMock.mockResolvedValue({
      id: "config-1",
      name: "OpenAI 备用线路",
      base_url: "https://api.openai.com/v1",
      api_key: "sk-updated",
      model: "gpt-4.1-mini",
      enabled: false,
      created_at: "2026-04-06T00:00:00Z",
      updated_at: "2026-04-06T02:00:00Z",
    });

    render(<AdminModelsPage />);

    fireEvent.change(await screen.findByLabelText("配置名称 OpenAI 主线路由"), {
      target: { value: "OpenAI 备用线路" },
    });
    fireEvent.change(screen.getByLabelText("模型 ID OpenAI 主线路由"), {
      target: { value: "gpt-4.1-mini" },
    });
    fireEvent.click(screen.getByLabelText("启用 OpenAI 主线路由"));
    fireEvent.click(screen.getByRole("button", { name: "保存 OpenAI 主线路由" }));

    await waitFor(() => {
      expect(updateAdminModelConfigMock).toHaveBeenCalledWith(
        "config-1",
        {
          name: "OpenAI 备用线路",
          base_url: "https://api.openai.com/v1",
          api_key: "sk-live-1",
          model: "gpt-4.1-mini",
          enabled: false,
        },
        "token-1",
      );
    });

    expect(screen.getByDisplayValue("OpenAI 备用线路")).toBeInTheDocument();
  });

  it("deletes an existing model config", async () => {
    deleteAdminModelConfigMock.mockResolvedValue(undefined);

    render(<AdminModelsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "删除 OpenAI 主线路由" }));

    await waitFor(() => {
      expect(deleteAdminModelConfigMock).toHaveBeenCalledWith("config-1", "token-1");
    });
    expect(screen.queryByDisplayValue("OpenAI 主线路由")).not.toBeInTheDocument();
  });
});
