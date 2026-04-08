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
          recommended_scene: "general",
          recommended_usage: "适合通用产品讨论。",
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
    expect(screen.getByText("推荐结果预览")).toBeInTheDocument();
    expect(screen.getByText("恢复链路预演")).toBeInTheDocument();
    expect(screen.getAllByText("通用对话").length).toBeGreaterThan(0);
    expect(screen.getAllByText("当前推荐：OpenAI 主线路由").length).toBeGreaterThan(0);
    expect(screen.getAllByText("原因：当前可用模型里，它与该场景最匹配。").length).toBeGreaterThan(0);
    expect(screen.getByText("如果当前坏掉的是通用对话模型")).toBeInTheDocument();

    await waitFor(() => {
      expect(listAdminModelConfigsMock).toHaveBeenCalledWith("token-1");
    });
    expect(screen.getByDisplayValue("OpenAI 主线路由")).toBeInTheDocument();
  });

  it("updates recommendation preview immediately when editing scene configuration", async () => {
    listAdminModelConfigsMock.mockResolvedValue({
      items: [
        {
          id: "config-1",
          name: "OpenAI 主线路由",
          recommended_scene: "general",
          recommended_usage: "适合通用产品讨论。",
          base_url: "https://api.openai.com/v1",
          api_key: "sk-live-1",
          model: "gpt-4.1",
          enabled: true,
          created_at: "2026-04-06T00:00:00Z",
          updated_at: "2026-04-06T00:00:00Z",
        },
        {
          id: "config-2",
          name: "Claude 推理线路",
          recommended_scene: "reasoning",
          recommended_usage: "适合承接长文本推理。",
          base_url: "https://api.anthropic.com/v1",
          api_key: "sk-claude-1",
          model: "claude-3-7-sonnet",
          enabled: true,
          created_at: "2026-04-06T01:00:00Z",
          updated_at: "2026-04-06T01:00:00Z",
        },
      ],
    });

    render(<AdminModelsPage />);

    expect(await screen.findByText("当前推荐：Claude 推理线路")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("推荐场景 OpenAI 主线路由"), {
      target: { value: "reasoning" },
    });

    expect(screen.getAllByText("当前推荐：OpenAI 主线路由").length).toBeGreaterThan(0);
    expect(
      screen.getByText("原因：它和当前场景一致，且在同场景候选里排序更靠前。"),
    ).toBeInTheDocument();
  });

  it("updates recovery simulation immediately when editing scene configuration", async () => {
    listAdminModelConfigsMock.mockResolvedValue({
      items: [
        {
          id: "config-1",
          name: "OpenAI 主线路由",
          recommended_scene: "general",
          recommended_usage: "适合通用产品讨论。",
          base_url: "https://api.openai.com/v1",
          api_key: "sk-live-1",
          model: "gpt-4.1",
          enabled: true,
          created_at: "2026-04-06T00:00:00Z",
          updated_at: "2026-04-06T00:00:00Z",
        },
        {
          id: "config-2",
          name: "Claude 推理线路",
          recommended_scene: "reasoning",
          recommended_usage: "适合承接长文本推理。",
          base_url: "https://api.anthropic.com/v1",
          api_key: "sk-claude-1",
          model: "claude-3-7-sonnet",
          enabled: true,
          created_at: "2026-04-06T01:00:00Z",
          updated_at: "2026-04-06T01:00:00Z",
        },
      ],
    });

    render(<AdminModelsPage />);

    expect(await screen.findByText("如果当前坏掉的是长文本推理模型")).toBeInTheDocument();
    expect(screen.getAllByText("恢复推荐：Claude 推理线路").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("推荐场景 OpenAI 主线路由"), {
      target: { value: "reasoning" },
    });

    expect(screen.getAllByText("恢复推荐：OpenAI 主线路由").length).toBeGreaterThan(0);
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
      recommended_scene: "general",
      recommended_usage: "适合多轮澄清。",
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
    fireEvent.change(screen.getByLabelText("新推荐用途"), {
      target: { value: "适合多轮澄清。" },
    });
    fireEvent.change(screen.getByLabelText("新推荐场景"), {
      target: { value: "general" },
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
          recommended_scene: "general",
          recommended_usage: "适合多轮澄清。",
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
      recommended_scene: "reasoning",
      recommended_usage: "适合快速补充细节。",
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
    fireEvent.change(screen.getByLabelText("推荐用途 OpenAI 主线路由"), {
      target: { value: "适合快速补充细节。" },
    });
    fireEvent.change(screen.getByLabelText("推荐场景 OpenAI 主线路由"), {
      target: { value: "reasoning" },
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
          recommended_scene: "reasoning",
          recommended_usage: "适合快速补充细节。",
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

  it("shows create error and keeps form values when creation fails", async () => {
    createAdminModelConfigMock.mockRejectedValue(new Error("创建失败"));

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
    fireEvent.change(screen.getByLabelText("新推荐用途"), {
      target: { value: "适合多轮澄清。" },
    });
    fireEvent.change(screen.getByLabelText("新推荐场景"), {
      target: { value: "general" },
    });
    fireEvent.change(screen.getByLabelText("新模型 ID"), {
      target: { value: "gpt-4o-mini" },
    });
    fireEvent.click(screen.getByLabelText("新配置启用"));
    fireEvent.click(screen.getByRole("button", { name: "创建模型配置" }));

    expect(await screen.findByText("创建失败")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Azure OpenAI")).toBeInTheDocument();
    expect(screen.getByDisplayValue("https://azure.example.com/openai")).toBeInTheDocument();
    expect(screen.getByDisplayValue("sk-azure")).toBeInTheDocument();
    expect(screen.getByDisplayValue("适合多轮澄清。")).toBeInTheDocument();
    expect(screen.getByDisplayValue("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByLabelText("新配置启用")).toBeChecked();
  });

  it("disables create button while creating and blocks duplicate submit", async () => {
    let resolveCreate: ((value: {
      id: string;
      name: string;
      recommended_scene?: string | null;
      recommended_usage?: string | null;
      base_url: string;
      api_key: string;
      model: string;
      enabled: boolean;
      created_at: string;
      updated_at: string;
    }) => void) | undefined;

    createAdminModelConfigMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve;
        }),
    );

    render(<AdminModelsPage />);

    fireEvent.change(await screen.findByLabelText("新配置名称"), {
      target: { value: "Azure OpenAI" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建模型配置" }));

    const creatingButton = await screen.findByRole("button", { name: "创建中..." });
    expect(screen.getByLabelText("新配置名称")).toBeDisabled();
    expect(screen.getByLabelText("新 Base URL")).toBeDisabled();
    expect(screen.getByLabelText("新 API Key")).toBeDisabled();
    expect(screen.getByLabelText("新推荐场景")).toBeDisabled();
    expect(screen.getByLabelText("新推荐用途")).toBeDisabled();
    expect(screen.getByLabelText("新模型 ID")).toBeDisabled();
    expect(screen.getByLabelText("新配置启用")).toBeDisabled();
    expect(creatingButton).toBeDisabled();
    expect(createAdminModelConfigMock).toHaveBeenCalledTimes(1);

    fireEvent.click(creatingButton);
    expect(createAdminModelConfigMock).toHaveBeenCalledTimes(1);

    resolveCreate?.({
      id: "config-2",
      name: "Azure OpenAI",
      recommended_scene: "general",
      recommended_usage: "",
      base_url: "https://azure.example.com/openai",
      api_key: "sk-azure",
      model: "gpt-4o-mini",
      enabled: false,
      created_at: "2026-04-06T01:00:00Z",
      updated_at: "2026-04-06T01:00:00Z",
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "创建模型配置" })).toBeEnabled();
    });
  });

  it("shows update error when update request fails", async () => {
    updateAdminModelConfigMock.mockRejectedValue(new Error("更新失败"));

    render(<AdminModelsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "保存 OpenAI 主线路由" }));

    expect(await screen.findByText("更新失败")).toBeInTheDocument();
    expect(screen.getByDisplayValue("OpenAI 主线路由")).toBeInTheDocument();
  });

  it("disables save and delete while updating and blocks duplicate submit", async () => {
    let resolveUpdate:
      | ((value: {
          id: string;
          name: string;
          recommended_scene?: string | null;
          recommended_usage?: string | null;
          base_url: string;
          api_key: string;
          model: string;
          enabled: boolean;
          created_at: string;
          updated_at: string;
        }) => void)
      | undefined;

    updateAdminModelConfigMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpdate = resolve;
        }),
    );

    render(<AdminModelsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "保存 OpenAI 主线路由" }));

    const savingButton = await screen.findByRole("button", { name: "保存中..." });
    const deleteButton = screen.getByRole("button", { name: "删除 OpenAI 主线路由" });
    expect(screen.getByLabelText("配置名称 OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("Base URL OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("API Key OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("推荐场景 OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("推荐用途 OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("模型 ID OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("启用 OpenAI 主线路由")).toBeDisabled();
    expect(savingButton).toBeDisabled();
    expect(deleteButton).toBeDisabled();
    expect(updateAdminModelConfigMock).toHaveBeenCalledTimes(1);

    fireEvent.click(savingButton);
    fireEvent.click(deleteButton);
    expect(updateAdminModelConfigMock).toHaveBeenCalledTimes(1);
    expect(deleteAdminModelConfigMock).not.toHaveBeenCalled();

    resolveUpdate?.({
      id: "config-1",
      name: "OpenAI 主线路由",
      recommended_scene: "general",
      recommended_usage: "适合通用产品讨论。",
      base_url: "https://api.openai.com/v1",
      api_key: "sk-live-1",
      model: "gpt-4.1",
      enabled: true,
      created_at: "2026-04-06T00:00:00Z",
      updated_at: "2026-04-06T02:00:00Z",
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "保存 OpenAI 主线路由" })).toBeEnabled();
    });
  });

  it("shows delete error and keeps item when delete request fails", async () => {
    deleteAdminModelConfigMock.mockRejectedValue(new Error("删除失败"));

    render(<AdminModelsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "删除 OpenAI 主线路由" }));

    expect(await screen.findByText("删除失败")).toBeInTheDocument();
    expect(screen.getByDisplayValue("OpenAI 主线路由")).toBeInTheDocument();
  });

  it("disables save and delete while deleting and blocks duplicate submit", async () => {
    let resolveDelete: (() => void) | undefined;

    deleteAdminModelConfigMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        }),
    );

    render(<AdminModelsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "删除 OpenAI 主线路由" }));

    const deletingButton = await screen.findByRole("button", { name: "删除中..." });
    const saveButton = screen.getByRole("button", { name: "保存 OpenAI 主线路由" });
    expect(screen.getByLabelText("配置名称 OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("Base URL OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("API Key OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("推荐场景 OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("推荐用途 OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("模型 ID OpenAI 主线路由")).toBeDisabled();
    expect(screen.getByLabelText("启用 OpenAI 主线路由")).toBeDisabled();
    expect(deletingButton).toBeDisabled();
    expect(saveButton).toBeDisabled();
    expect(deleteAdminModelConfigMock).toHaveBeenCalledTimes(1);

    fireEvent.click(deletingButton);
    fireEvent.click(saveButton);
    expect(deleteAdminModelConfigMock).toHaveBeenCalledTimes(1);
    expect(updateAdminModelConfigMock).not.toHaveBeenCalled();

    resolveDelete?.();

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "删除中..." })).not.toBeInTheDocument();
    });
  });
});
