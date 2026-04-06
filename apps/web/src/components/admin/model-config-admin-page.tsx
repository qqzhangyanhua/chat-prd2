"use client";

import { useEffect, useState } from "react";

import {
  createAdminModelConfig,
  deleteAdminModelConfig,
  listAdminModelConfigs,
  updateAdminModelConfig,
} from "../../lib/api";
import type { AdminModelConfigItem } from "../../lib/types";
import { useAuthStore } from "../../store/auth-store";

interface ModelConfigFormState {
  name: string;
  base_url: string;
  api_key: string;
  model: string;
  enabled: boolean;
}

const EMPTY_FORM: ModelConfigFormState = {
  name: "",
  base_url: "",
  api_key: "",
  model: "",
  enabled: false,
};

function toFormState(item: AdminModelConfigItem): ModelConfigFormState {
  return {
    name: item.name,
    base_url: item.base_url,
    api_key: item.api_key,
    model: item.model,
    enabled: item.enabled,
  };
}

export function ModelConfigAdminPage() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const [items, setItems] = useState<AdminModelConfigItem[]>([]);
  const [createForm, setCreateForm] = useState<ModelConfigFormState>(EMPTY_FORM);
  const [editForms, setEditForms] = useState<Record<string, ModelConfigFormState>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
    const created = await createAdminModelConfig(createForm, accessToken);
    setItems((current) => [...current, created]);
    setEditForms((current) => ({
      ...current,
      [created.id]: toFormState(created),
    }));
    setCreateForm(EMPTY_FORM);
  }

  async function handleUpdate(itemId: string) {
    const draft = editForms[itemId];
    if (!draft) {
      return;
    }

    const updated = await updateAdminModelConfig(itemId, draft, accessToken);
    setItems((current) => current.map((item) => (item.id === itemId ? updated : item)));
    setEditForms((current) => ({
      ...current,
      [itemId]: toFormState(updated),
    }));
  }

  async function handleDelete(itemId: string) {
    await deleteAdminModelConfig(itemId, accessToken);
    setItems((current) => current.filter((item) => item.id !== itemId));
    setEditForms((current) => {
      const next = { ...current };
      delete next[itemId];
      return next;
    });
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
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, api_key: event.target.value }))
              }
              value={createForm.api_key}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            新模型 ID
            <input
              className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
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
            onChange={(event) =>
              setCreateForm((current) => ({ ...current, enabled: event.target.checked }))
            }
            type="checkbox"
          />
          新配置启用
        </label>

        <button
          className="mt-4 rounded-xl bg-stone-950 px-4 py-2 text-sm font-medium text-white"
          onClick={() => void handleCreate()}
          type="button"
        >
          创建模型配置
        </button>
      </section>

      <section className="flex flex-col gap-4">
        {items.map((item) => {
          const draft = editForms[item.id] ?? toFormState(item);

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
                  {`模型 ID ${item.name}`}
                  <input
                    className="rounded-xl border border-stone-200 px-3 py-2 text-sm text-stone-950"
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
                  onClick={() => void handleUpdate(item.id)}
                  type="button"
                >
                  {`保存 ${item.name}`}
                </button>
                <button
                  className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-600"
                  onClick={() => void handleDelete(item.id)}
                  type="button"
                >
                  {`删除 ${item.name}`}
                </button>
              </div>
            </article>
          );
        })}
      </section>
    </main>
  );
}
