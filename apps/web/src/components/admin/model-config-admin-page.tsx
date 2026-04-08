"use client";

import { useEffect, useState } from "react";

import {
  createAdminModelConfig,
  deleteAdminModelConfig,
  listAdminModelConfigs,
  updateAdminModelConfig,
} from "../../lib/api";
import type {
  AdminModelConfigCreateRequest,
  AdminModelConfigItem,
  AdminModelConfigUpdateRequest,
  RecommendedScene,
} from "../../lib/types";
import { useAuthStore } from "../../store/auth-store";

interface ModelConfigFormState {
  name: string;
  recommended_scene: RecommendedScene;
  recommended_usage: string;
  base_url: string;
  api_key: string;
  model: string;
  enabled: boolean;
}

interface PreviewModelConfig {
  id: string;
  name: string;
  recommended_scene: RecommendedScene;
  recommended_usage: string;
  model: string;
  enabled: boolean;
}

const EMPTY_FORM: ModelConfigFormState = {
  name: "",
  recommended_scene: "general",
  recommended_usage: "",
  base_url: "",
  api_key: "",
  model: "",
  enabled: false,
};

function toFormState(item: AdminModelConfigItem): ModelConfigFormState {
  return {
    name: item.name,
    recommended_scene: item.recommended_scene ?? "general",
    recommended_usage: item.recommended_usage ?? "",
    base_url: item.base_url,
    api_key: item.api_key,
    model: item.model,
    enabled: item.enabled,
  };
}

function buildCreatePayload(form: ModelConfigFormState): AdminModelConfigCreateRequest {
  const recommendedUsage = form.recommended_usage.trim();
  return {
    name: form.name,
    recommended_scene: form.recommended_scene,
    base_url: form.base_url,
    api_key: form.api_key,
    model: form.model,
    enabled: form.enabled,
    ...(recommendedUsage ? { recommended_usage: recommendedUsage } : {}),
  };
}

function buildUpdatePayload(form: ModelConfigFormState): AdminModelConfigUpdateRequest {
  const recommendedUsage = form.recommended_usage.trim();
  return {
    name: form.name,
    recommended_scene: form.recommended_scene,
    base_url: form.base_url,
    api_key: form.api_key,
    model: form.model,
    enabled: form.enabled,
    ...(recommendedUsage ? { recommended_usage: recommendedUsage } : {}),
  };
}

function inferModelScene(modelConfig: PreviewModelConfig | null): RecommendedScene {
  if (!modelConfig) {
    return "general";
  }

  if (modelConfig.recommended_scene) {
    return modelConfig.recommended_scene;
  }

  const haystack = [modelConfig.recommended_usage, modelConfig.name, modelConfig.model]
    .join(" ")
    .toLowerCase();
  if (
    haystack.includes("长文本") ||
    haystack.includes("推理") ||
    haystack.includes("reason") ||
    haystack.includes("claude") ||
    haystack.includes("sonnet")
  ) {
    return "reasoning";
  }
  if (
    haystack.includes("通用") ||
    haystack.includes("对话") ||
    haystack.includes("chat") ||
    haystack.includes("gpt")
  ) {
    return "general";
  }
  return "fallback";
}

function inferModelFamily(modelConfig: PreviewModelConfig | null): string {
  if (!modelConfig) {
    return "any";
  }

  const haystack = [modelConfig.name, modelConfig.model].join(" ").toLowerCase();
  if (haystack.includes("claude") || haystack.includes("sonnet")) {
    return "claude";
  }
  if (haystack.includes("gpt") || haystack.includes("openai")) {
    return "gpt";
  }
  return "other";
}

function getSceneRankForTarget(
  candidateScene: RecommendedScene,
  targetScene: RecommendedScene,
): number {
  const rankMap: Record<RecommendedScene, Record<RecommendedScene, number>> = {
    general: { general: 0, reasoning: 1, fallback: 2 },
    reasoning: { reasoning: 0, general: 1, fallback: 2 },
    fallback: { fallback: 0, general: 1, reasoning: 2 },
  };
  return rankMap[targetScene][candidateScene];
}

function sortAvailableModels(
  models: PreviewModelConfig[],
  targetScene: RecommendedScene,
): PreviewModelConfig[] {
  const targetFamily = targetScene === "reasoning" ? "claude" : targetScene === "general" ? "gpt" : "any";

  return [...models].sort((left, right) => {
    const leftScene = inferModelScene(left);
    const rightScene = inferModelScene(right);
    const leftSceneRank = getSceneRankForTarget(leftScene, targetScene);
    const rightSceneRank = getSceneRankForTarget(rightScene, targetScene);
    if (leftSceneRank !== rightSceneRank) {
      return leftSceneRank - rightSceneRank;
    }

    const leftFamilyRank = targetFamily !== "any" && inferModelFamily(left) === targetFamily ? 0 : 1;
    const rightFamilyRank = targetFamily !== "any" && inferModelFamily(right) === targetFamily ? 0 : 1;
    if (leftFamilyRank !== rightFamilyRank) {
      return leftFamilyRank - rightFamilyRank;
    }

    const leftName = left.name.toLowerCase();
    const rightName = right.name.toLowerCase();
    if (leftName !== rightName) {
      return leftName.localeCompare(rightName);
    }
    return left.id.localeCompare(right.id);
  });
}

function getSceneLabel(scene: RecommendedScene): string {
  if (scene === "general") {
    return "通用对话";
  }
  if (scene === "reasoning") {
    return "长文本推理";
  }
  return "兜底回退";
}

function buildPreviewReason(
  rankedModels: PreviewModelConfig[],
  targetScene: RecommendedScene,
): string {
  const recommended = rankedModels[0] ?? null;
  if (!recommended) {
    return "当前没有启用模型，无法生成推荐。";
  }

  const recommendedScene = inferModelScene(recommended);
  if (recommendedScene === targetScene) {
    if (rankedModels.length === 1) {
      return "当前可用模型里，它与该场景最匹配。";
    }
    return "它和当前场景一致，且在同场景候选里排序更靠前。";
  }

  const recommendedFamily = inferModelFamily(recommended);
  if (
    (targetScene === "general" && recommendedFamily === "gpt") ||
    (targetScene === "reasoning" && recommendedFamily === "claude")
  ) {
    return "虽然没有完全同场景候选，但它的模型家族更贴近该场景。";
  }

  return "缺少更合适的同场景候选，所以回退到当前最稳妥的可用模型。";
}

function buildRecoveryReason(
  rankedModels: PreviewModelConfig[],
  targetScene: RecommendedScene,
): string {
  const recommended = rankedModels[0] ?? null;
  if (!recommended) {
    return "当前没有启用模型，恢复时无法自动推荐。";
  }

  const recommendedScene = inferModelScene(recommended);
  if (recommendedScene === targetScene) {
    return "恢复时会优先选择同场景候选，当前它排在最前面。";
  }

  return "当前缺少更合适的同场景候选，恢复时会回退到这个可用模型。";
}

export function ModelConfigAdminPage() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const [items, setItems] = useState<AdminModelConfigItem[]>([]);
  const [createForm, setCreateForm] = useState<ModelConfigFormState>(EMPTY_FORM);
  const [editForms, setEditForms] = useState<Record<string, ModelConfigFormState>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [pendingActionById, setPendingActionById] = useState<
    Record<string, "saving" | "deleting" | null>
  >({});
  const previewModels: PreviewModelConfig[] = items
    .map((item) => {
      const draft = editForms[item.id] ?? toFormState(item);
      return {
        id: item.id,
        name: draft.name,
        recommended_scene: draft.recommended_scene,
        recommended_usage: draft.recommended_usage,
        model: draft.model,
        enabled: draft.enabled,
      };
    })
    .filter((item) => item.enabled);
  const createPreviewName = createForm.name.trim();
  const createPreviewModel = createForm.model.trim();
  if (createPreviewName && createPreviewModel && createForm.enabled) {
    previewModels.unshift({
      id: "__draft__",
      name: `${createPreviewName}（未保存）`,
      recommended_scene: createForm.recommended_scene,
      recommended_usage: createForm.recommended_usage,
      model: createPreviewModel,
      enabled: true,
    });
  }
  const previewScenes: RecommendedScene[] = ["general", "reasoning", "fallback"];

  useEffect(() => {
    if (!user?.is_admin) {
      return;
    }

    let cancelled = false;

    async function loadItems() {
      try {
        setErrorMessage(null);
        const response = await listAdminModelConfigs(accessToken);

        if (cancelled) {
          return;
        }

        setItems(response.items);
        setEditForms(
          Object.fromEntries(response.items.map((item) => [item.id, toFormState(item)])),
        );
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "模型配置加载失败");
        }
      }
    }

    void loadItems();

    return () => {
      cancelled = true;
    };
  }, [accessToken, user?.is_admin]);

  if (!user?.is_admin) {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-16">
        <div className="w-full rounded-3xl border border-red-200 bg-red-50 p-8 text-center">
          <h1 className="text-2xl font-semibold text-red-700">访问受限</h1>
          <p className="mt-3 text-sm text-red-600">仅管理员可访问模型管理页面。</p>
        </div>
      </main>
    );
  }

  async function handleCreate() {
    if (isCreating) {
      return;
    }

    try {
      setIsCreating(true);
      setErrorMessage(null);

      const created = await createAdminModelConfig(buildCreatePayload(createForm), accessToken);
      setItems((current) => [...current, created]);
      setEditForms((current) => ({
        ...current,
        [created.id]: toFormState(created),
      }));
      setCreateForm(EMPTY_FORM);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "创建模型配置失败");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleUpdate(itemId: string) {
    const draft = editForms[itemId];
    if (!draft || pendingActionById[itemId]) {
      return;
    }

    try {
      setPendingActionById((current) => ({
        ...current,
        [itemId]: "saving",
      }));
      setErrorMessage(null);

      const updated = await updateAdminModelConfig(itemId, buildUpdatePayload(draft), accessToken);
      setItems((current) => current.map((item) => (item.id === itemId ? updated : item)));
      setEditForms((current) => ({
        ...current,
        [itemId]: toFormState(updated),
      }));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "更新模型配置失败");
    } finally {
      setPendingActionById((current) => ({
        ...current,
        [itemId]: null,
      }));
    }
  }

  async function handleDelete(itemId: string) {
    if (pendingActionById[itemId]) {
      return;
    }

    try {
      setPendingActionById((current) => ({
        ...current,
        [itemId]: "deleting",
      }));
      setErrorMessage(null);

      await deleteAdminModelConfig(itemId, accessToken);
      setItems((current) => current.filter((item) => item.id !== itemId));
      setEditForms((current) => {
        const next = { ...current };
        delete next[itemId];
        return next;
      });
      setPendingActionById((current) => {
        const next = { ...current };
        delete next[itemId];
        return next;
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "删除模型配置失败");
      setPendingActionById((current) => ({
        ...current,
        [itemId]: null,
      }));
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-10">
      <header className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        <h1 className="text-3xl font-semibold text-stone-950">模型管理</h1>
        <p className="mt-2 text-sm text-stone-600">
          管理管理员可用的模型配置，支持新增、编辑、删除与启停。
        </p>
      </header>

      {errorMessage ? (
        <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {errorMessage}
        </p>
      ) : null}

      <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-stone-950">创建模型配置</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            新配置名称
            <input
              className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
              disabled={isCreating}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, name: event.target.value }))
              }
              value={createForm.name}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            新 Base URL
            <input
              className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
              disabled={isCreating}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, base_url: event.target.value }))
              }
              value={createForm.base_url}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            新 API Key
            <input
              className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
              disabled={isCreating}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, api_key: event.target.value }))
              }
              value={createForm.api_key}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            新推荐场景
            <select
              className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
              disabled={isCreating}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  recommended_scene: event.target.value as RecommendedScene,
                }))
              }
              value={createForm.recommended_scene}
            >
              <option value="general">通用对话</option>
              <option value="reasoning">长文本推理</option>
              <option value="fallback">兜底回退</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            新推荐用途
            <textarea
              className="min-h-24 rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
              disabled={isCreating}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  recommended_usage: event.target.value,
                }))
              }
              value={createForm.recommended_usage}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            新模型 ID
            <input
              className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
              disabled={isCreating}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, model: event.target.value }))
              }
              value={createForm.model}
            />
          </label>
        </div>

        <label className="mt-4 flex items-center gap-2 text-sm text-stone-700">
          <input
            checked={createForm.enabled}
            disabled={isCreating}
            onChange={(event) =>
              setCreateForm((current) => ({ ...current, enabled: event.target.checked }))
            }
            type="checkbox"
          />
          新配置启用
        </label>

        <button
          className="mt-4 rounded-xl bg-stone-950 px-4 py-2 text-sm font-medium text-white"
          disabled={isCreating}
          onClick={() => void handleCreate()}
          type="button"
        >
          {isCreating ? "创建中..." : "创建模型配置"}
        </button>
      </section>

      <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-stone-950">推荐结果预览</h2>
        <p className="mt-2 text-sm text-stone-600">
          按当前排序策略预估三种场景下会优先推荐哪个模型。未保存且已启用的创建草稿也会参与预览。
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {previewScenes.map((scene) => {
            const ranked = sortAvailableModels(previewModels, scene);
            const recommended = ranked[0] ?? null;
            const previewReason = buildPreviewReason(ranked, scene);
            return (
              <article
                className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4"
                key={scene}
              >
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                  {getSceneLabel(scene)}
                </p>
                <p className="mt-2 text-sm font-medium text-stone-950">
                  {recommended ? `当前推荐：${recommended.name}` : "当前推荐：暂无可用模型"}
                </p>
                <p className="mt-1 text-xs text-stone-500">
                  {recommended ? `模型 ID：${recommended.model}` : "请先启用至少一个模型配置。"}
                </p>
                <p className="mt-2 text-xs text-stone-600">{`原因：${previewReason}`}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-stone-950">恢复链路预演</h2>
        <p className="mt-2 text-sm text-stone-600">
          模拟当前坏掉的是某一类模型时，系统会把用户恢复到哪个可用模型。
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {previewScenes.map((scene) => {
            const ranked = sortAvailableModels(previewModels, scene);
            const recommended = ranked[0] ?? null;
            const recoveryReason = buildRecoveryReason(ranked, scene);
            return (
              <article
                className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4"
                key={`recovery-${scene}`}
              >
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                  {`如果当前坏掉的是${getSceneLabel(scene)}模型`}
                </p>
                <p className="mt-2 text-sm font-medium text-stone-950">
                  {recommended ? `恢复推荐：${recommended.name}` : "恢复推荐：暂无可用模型"}
                </p>
                <p className="mt-1 text-xs text-stone-500">
                  {recommended ? `模型 ID：${recommended.model}` : "请先启用至少一个模型配置。"}
                </p>
                <p className="mt-2 text-xs text-stone-600">{`原因：${recoveryReason}`}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="flex flex-col gap-4">
        {items.map((item) => {
          const draft = editForms[item.id] ?? toFormState(item);
          const pendingAction = pendingActionById[item.id];
          const isSaving = pendingAction === "saving";
          const isDeleting = pendingAction === "deleting";

          return (
            <article
              className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm"
              key={item.id}
            >
              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm text-stone-700">
                  {`配置名称 ${item.name}`}
                  <input
                    className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
                    disabled={isSaving || isDeleting}
                    onChange={(event) =>
                      setEditForms((current) => ({
                        ...current,
                        [item.id]: { ...draft, name: event.target.value },
                      }))
                    }
                    value={draft.name}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-stone-700">
                  {`Base URL ${item.name}`}
                  <input
                    className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
                    disabled={isSaving || isDeleting}
                    onChange={(event) =>
                      setEditForms((current) => ({
                        ...current,
                        [item.id]: { ...draft, base_url: event.target.value },
                      }))
                    }
                    value={draft.base_url}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-stone-700">
                  {`API Key ${item.name}`}
                  <input
                    className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
                    disabled={isSaving || isDeleting}
                    onChange={(event) =>
                      setEditForms((current) => ({
                        ...current,
                        [item.id]: { ...draft, api_key: event.target.value },
                      }))
                    }
                    value={draft.api_key}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-stone-700">
                  {`推荐场景 ${item.name}`}
                  <select
                    className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
                    disabled={isSaving || isDeleting}
                    onChange={(event) =>
                      setEditForms((current) => ({
                        ...current,
                        [item.id]: {
                          ...draft,
                          recommended_scene: event.target.value as RecommendedScene,
                        },
                      }))
                    }
                    value={draft.recommended_scene}
                  >
                    <option value="general">通用对话</option>
                    <option value="reasoning">长文本推理</option>
                    <option value="fallback">兜底回退</option>
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-sm text-stone-700">
                  {`推荐用途 ${item.name}`}
                  <textarea
                    className="min-h-24 rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
                    disabled={isSaving || isDeleting}
                    onChange={(event) =>
                      setEditForms((current) => ({
                        ...current,
                        [item.id]: { ...draft, recommended_usage: event.target.value },
                      }))
                    }
                    value={draft.recommended_usage}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-stone-700">
                  {`模型 ID ${item.name}`}
                  <input
                    className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
                    disabled={isSaving || isDeleting}
                    onChange={(event) =>
                      setEditForms((current) => ({
                        ...current,
                        [item.id]: { ...draft, model: event.target.value },
                      }))
                    }
                    value={draft.model}
                  />
                </label>
              </div>

              <label className="mt-4 flex items-center gap-2 text-sm text-stone-700">
                <input
                  checked={draft.enabled}
                  disabled={isSaving || isDeleting}
                  onChange={(event) =>
                    setEditForms((current) => ({
                      ...current,
                      [item.id]: { ...draft, enabled: event.target.checked },
                    }))
                  }
                  type="checkbox"
                />
                {`启用 ${item.name}`}
              </label>

              <div className="mt-4 flex gap-3">
                <button
                  className="rounded-xl bg-stone-950 px-4 py-2 text-sm font-medium text-white"
                  disabled={isSaving || isDeleting}
                  onClick={() => void handleUpdate(item.id)}
                  type="button"
                >
                  {isSaving ? "保存中..." : `保存 ${item.name}`}
                </button>
                <button
                  className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-600"
                  disabled={isSaving || isDeleting}
                  onClick={() => void handleDelete(item.id)}
                  type="button"
                >
                  {isDeleting ? "删除中..." : `删除 ${item.name}`}
                </button>
              </div>
            </article>
          );
        })}
      </section>
    </main>
  );
}
