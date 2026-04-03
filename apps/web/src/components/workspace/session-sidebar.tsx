"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  deleteSession,
  exportSession,
  getSession,
  listSessions,
  updateSession,
} from "../../lib/api";
import type { SessionResponse } from "../../lib/types";
import { useAuthStore } from "../../store/auth-store";
import { workspaceStore } from "../../store/workspace-store";

interface SessionSidebarProps {
  sessionId: string;
}

function formatRecentActivity(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "最近活跃时间未知";
  }

  const diffMs = Math.max(Date.now() - date.getTime(), 0);
  const diffMinutes = Math.floor(diffMs / (1000 * 60));

  if (diffMinutes < 1) {
    return "最近活跃 刚刚";
  }

  if (diffMinutes < 60) {
    return `最近活跃 ${diffMinutes} 分钟前`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `最近活跃 ${diffHours} 小时前`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `最近活跃 ${diffDays} 天前`;
}

export function SessionSidebar({ sessionId }: SessionSidebarProps) {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [titleDraft, setTitleDraft] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSessions() {
      try {
        const response = await listSessions(accessToken);
        if (!cancelled) {
          setSessions(response.sessions);
        }
      } catch {
        if (!cancelled) {
          setSessions([]);
        }
      }
    }

    void loadSessions();

    return () => {
      cancelled = true;
    };
  }, [accessToken, sessionId]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === sessionId) ?? null,
    [sessionId, sessions],
  );

  useEffect(() => {
    setTitleDraft(activeSession?.title ?? "");
    setRenameError(null);
  }, [activeSession]);

  async function handleExport() {
    const exported = await exportSession(sessionId, accessToken);
    if (
      typeof document === "undefined" ||
      typeof URL.createObjectURL !== "function" ||
      typeof URL.revokeObjectURL !== "function"
    ) {
      return;
    }

    const blob = new Blob([exported.content], { type: "text/markdown;charset=utf-8" });
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = exported.file_name;
    link.click();
    URL.revokeObjectURL(downloadUrl);
  }

  async function handleRecover() {
    const snapshot = await getSession(sessionId, accessToken);
    workspaceStore.getState().hydrateSession(snapshot);
  }

  async function handleRename() {
    const normalizedTitle = titleDraft.trim();

    if (!normalizedTitle) {
      setRenameError("会话标题不能为空");
      return;
    }

    try {
      setRenameError(null);
      const snapshot = await updateSession(sessionId, { title: normalizedTitle }, accessToken);
      setTitleDraft(snapshot.session.title);
      setSessions((current) =>
        current.map((session) =>
          session.id === sessionId ? { ...session, ...snapshot.session } : session,
        ),
      );
    } catch (error) {
      setRenameError(error instanceof Error ? error.message : "重命名失败，请稍后再试");
    }
  }

  async function handleDelete() {
    await deleteSession(sessionId, accessToken);
    router.push("/workspace");
  }

  return (
    <aside className="flex h-full flex-col rounded-[28px] border border-stone-200 bg-stone-50 p-5 shadow-sm">
      <div className="space-y-1 border-b border-stone-200 pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">
          Project Board
        </p>
        <h2 className="text-2xl font-semibold text-stone-950">会话工作台</h2>
        <p className="text-sm leading-6 text-stone-600">
          这里展示当前用户的真实会话，你可以恢复当前状态、导出 PRD，或者切到其他项目继续推进。
        </p>
      </div>

      <div className="mt-5 rounded-2xl border border-stone-200 bg-white p-4">
        <label className="grid gap-2 text-sm font-medium text-stone-900">
          会话标题
          <input
            className="rounded-2xl border border-stone-300 px-3 py-2 outline-none"
            value={titleDraft}
            onChange={(event) => setTitleDraft(event.target.value)}
          />
        </label>
        <button
          className="mt-3 rounded-2xl border border-stone-900 bg-stone-950 px-4 py-2 text-sm font-medium text-white"
          onClick={() => void handleRename()}
          type="button"
        >
          保存标题
        </button>
        {renameError ? <p className="mt-3 text-sm text-red-600">{renameError}</p> : null}
      </div>

      <button
        className="mt-5 rounded-2xl border border-stone-900 bg-stone-950 px-4 py-3 text-sm font-medium text-white"
        onClick={() => router.push("/workspace")}
        type="button"
      >
        新建会话
      </button>

      <div className="mt-3 grid gap-3">
        <button
          className="rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm font-medium text-stone-900"
          onClick={() => void handleRecover()}
          type="button"
        >
          恢复会话
        </button>
        <button
          className="rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm font-medium text-stone-900"
          onClick={() => void handleExport()}
          type="button"
        >
          导出 PRD
        </button>
        <button
          className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
          onClick={() => void handleDelete()}
          type="button"
        >
          删除会话
        </button>
      </div>

      <div className="mt-6 space-y-3">
        {sessions.map((session) => (
          <button
            key={session.id}
            className={`block w-full rounded-2xl border px-4 py-4 text-left transition ${
              session.id === sessionId
                ? "border-stone-900 bg-white shadow-sm"
                : "border-stone-200 bg-white/70"
            }`}
            onClick={() => router.push(`/workspace/${session.id}`)}
            type="button"
          >
            <p className="text-sm font-semibold text-stone-900">{session.title}</p>
            <p className="mt-2 text-xs leading-5 text-stone-500">{session.initial_idea}</p>
            <p className="mt-2 text-xs text-stone-500">{formatRecentActivity(session.updated_at)}</p>
          </button>
        ))}
      </div>

      <div className="mt-auto rounded-2xl border border-dashed border-stone-300 bg-white px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
          Active Session
        </p>
        <p className="mt-2 text-lg font-semibold text-stone-900">
          {activeSession?.title ?? sessionId}
        </p>
        <p className="mt-2 text-sm leading-6 text-stone-600">
          {activeSession ? formatRecentActivity(activeSession.updated_at) : "最近活跃时间未知"}
        </p>
      </div>
    </aside>
  );
}
