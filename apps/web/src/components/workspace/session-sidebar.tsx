"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Download, RotateCcw, Trash2, Check, Clock } from "lucide-react";

import {
  deleteSession,
  exportSession,
  getSession,
  listSessions,
  updateSession,
} from "../../lib/api";
import type { SessionResponse } from "../../lib/types";
import { useAuthStore } from "../../store/auth-store";
import { useToastStore } from "../../store/toast-store";
import { workspaceStore } from "../../store/workspace-store";

interface SessionSidebarProps {
  sessionId: string;
}

function formatRecentActivity(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "时间未知";
  }

  const diffMs = Math.max(Date.now() - date.getTime(), 0);
  const diffMinutes = Math.floor(diffMs / (1000 * 60));

  if (diffMinutes < 1) {
    return "刚刚活跃";
  }

  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} 小时前`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} 天前`;
}

export function SessionSidebar({ sessionId }: SessionSidebarProps) {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const showToast = useToastStore((state) => state.showToast);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [titleDraft, setTitleDraft] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [isRecovering, setIsRecovering] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);

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
    setDeleteError(null);
    setIsDeleting(false);
    setConfirmingDelete(false);
    setIsRecovering(false);
    setIsExporting(false);
    setIsRenaming(false);
  }, [activeSession]);

  async function handleExport() {
    if (isExporting) {
      return;
    }

    try {
      setIsExporting(true);
      showToast({
        id: `export-session-${sessionId}`,
        message: "正在导出 PRD...",
        tone: "info",
      });

      const exported = await exportSession(sessionId, accessToken);
      if (
        typeof document !== "undefined" &&
        typeof URL.createObjectURL === "function" &&
        typeof URL.revokeObjectURL === "function"
      ) {
        const blob = new Blob([exported.content], { type: "text/markdown;charset=utf-8" });
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = exported.file_name;
        link.click();
        URL.revokeObjectURL(downloadUrl);
      }

      showToast({
        id: `export-session-${sessionId}`,
        message: "PRD 已导出",
        tone: "success",
      });
    } catch (error) {
      showToast({
        id: `export-session-${sessionId}`,
        message: error instanceof Error ? error.message : "导出失败，请稍后再试",
        tone: "error",
      });
    } finally {
      setIsExporting(false);
    }
  }

  async function handleRecover() {
    if (isRecovering) {
      return;
    }

    try {
      setIsRecovering(true);
      showToast({
        id: `recover-session-${sessionId}`,
        message: "正在恢复会话...",
        tone: "info",
      });

      const snapshot = await getSession(sessionId, accessToken);
      workspaceStore.getState().hydrateSession(snapshot);

      showToast({
        id: `recover-session-${sessionId}`,
        message: "会话已恢复",
        tone: "success",
      });
    } catch (error) {
      showToast({
        id: `recover-session-${sessionId}`,
        message: error instanceof Error ? error.message : "恢复失败，请稍后再试",
        tone: "error",
      });
    } finally {
      setIsRecovering(false);
    }
  }

  async function handleRename() {
    if (isRenaming) {
      return;
    }

    const normalizedTitle = titleDraft.trim();

    if (!normalizedTitle) {
      setRenameError("会话标题不能为空");
      return;
    }

    try {
      setRenameError(null);
      setIsRenaming(true);
      showToast({
        id: `rename-session-${sessionId}`,
        message: "正在保存标题...",
        tone: "info",
      });

      const snapshot = await updateSession(sessionId, { title: normalizedTitle }, accessToken);
      setTitleDraft(snapshot.session.title);
      setSessions((current) =>
        current.map((session) =>
          session.id === sessionId ? { ...session, ...snapshot.session } : session,
        ),
      );

      showToast({
        id: `rename-session-${sessionId}`,
        message: "标题已更新",
        tone: "success",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "重命名失败，请稍后再试";
      setRenameError(message);
      showToast({
        id: `rename-session-${sessionId}`,
        message,
        tone: "error",
      });
    } finally {
      setIsRenaming(false);
    }
  }

  async function handleDelete() {
    if (isDeleting) {
      return;
    }

    // confirmation handled by UI — no window.confirm
    try {
      setDeleteError(null);
      setIsDeleting(true);
      showToast({
        id: `delete-session-${sessionId}`,
        message: "正在删除会话...",
        tone: "info",
      });
      await deleteSession(sessionId, accessToken);
      showToast({
        id: `delete-session-${sessionId}`,
        message: "会话已删除",
        tone: "success",
      });
      router.push("/workspace");
    } catch (error) {
      const message = error instanceof Error ? error.message : "删除失败，请稍后再试";
      setDeleteError(message);
      setIsDeleting(false);
      showToast({
        id: `delete-session-${sessionId}`,
        message,
        tone: "error",
      });
    }
  }

  return (
    <aside className="flex h-full flex-col gap-4 rounded-2xl border border-stone-200/80 bg-white/90 p-4 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">

      {/* Active session info */}
      <div className="rounded-xl border border-stone-200 bg-stone-50 p-3.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400">
          Active Session
        </p>
        <p className="mt-1.5 truncate text-sm font-semibold text-stone-950">
          {activeSession?.title ?? sessionId}
        </p>
        {activeSession ? (
          <div className="mt-1.5 flex items-center gap-1.5 text-xs text-stone-400">
            <Clock className="h-3 w-3" />
            <span>{formatRecentActivity(activeSession.updated_at)}</span>
          </div>
        ) : null}
      </div>

      {/* Rename */}
      <div className="flex flex-col gap-2">
        <label className="flex flex-col gap-1.5 text-sm font-medium text-stone-700">
          重命名
          <input
            className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 outline-none transition-all duration-150 hover:border-stone-300 focus:border-stone-900 focus:bg-white focus:ring-2 focus:ring-stone-900/8"
            value={titleDraft}
            onChange={(event) => setTitleDraft(event.target.value)}
          />
        </label>
        <button
          className="flex cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-stone-950 px-3 py-2 text-xs font-semibold text-white transition-all duration-150 hover:bg-stone-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-stone-300"
          disabled={isRenaming}
          onClick={() => void handleRename()}
          type="button"
        >
          <Check className="h-3.5 w-3.5" />
          {isRenaming ? "保存中..." : "保存标题"}
        </button>
        {renameError ? (
          <p className="text-xs text-red-600">{renameError}</p>
        ) : null}
      </div>

      {/* Action buttons */}
      <div className="flex flex-col gap-2">
        <button
          className="flex cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-stone-950 px-3 py-2.5 text-xs font-semibold text-white transition-all duration-150 hover:bg-stone-800 active:scale-[0.98]"
          onClick={() => router.push("/workspace")}
          type="button"
        >
          <Plus className="h-3.5 w-3.5" />
          新建会话
        </button>

        <div className="grid grid-cols-2 gap-2">
          <button
            className="flex cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 transition-all duration-150 hover:border-stone-300 hover:bg-stone-50 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isRecovering}
            onClick={() => void handleRecover()}
            type="button"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            {isRecovering ? "恢复中..." : "恢复会话"}
          </button>
          <button
            className="flex cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 transition-all duration-150 hover:border-stone-300 hover:bg-stone-50 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isExporting}
            onClick={() => void handleExport()}
            type="button"
          >
            <Download className="h-3.5 w-3.5" />
            {isExporting ? "导出中..." : "导出 PRD"}
          </button>
        </div>
      </div>

      {/* Session list */}
      <div className="flex flex-col gap-1.5 overflow-y-auto">
        {sessions.map((session) => {
          const isActive = session.id === sessionId;
          const isDeletingCurrentSession = isActive && isDeleting;

          return (
            <button
              key={session.id}
              aria-label={`打开会话 ${session.title}`}
              className={`cursor-pointer rounded-xl border px-3 py-3 text-left transition-all duration-150 ${
                isActive
                  ? "border-stone-900 bg-stone-950 text-white"
                  : "border-stone-100 bg-white/60 text-stone-700 hover:border-stone-200 hover:bg-white"
              } ${isDeletingCurrentSession ? "cursor-not-allowed opacity-60" : ""}`}
              disabled={isDeletingCurrentSession}
              onClick={() => router.push(`/workspace/${session.id}`)}
              type="button"
            >
              <div className="flex items-start justify-between gap-2">
                <p className={`truncate text-xs font-semibold ${isActive ? "text-white" : "text-stone-900"}`}>
                  {session.title}
                </p>
                {isDeletingCurrentSession ? (
                  <span className="shrink-0 text-[10px] text-red-400">删除中</span>
                ) : null}
              </div>
              <p className={`mt-1 line-clamp-2 text-[11px] leading-4 ${isActive ? "text-stone-400" : "text-stone-400"}`}>
                {session.initial_idea}
              </p>
              <p className={`mt-1.5 text-[10px] ${isActive ? "text-stone-500" : "text-stone-400"}`}>
                {formatRecentActivity(session.updated_at)}
              </p>
            </button>
          );
        })}
      </div>

      {/* Danger zone */}
      <div className="mt-auto border-t border-stone-100 pt-3">
        {confirmingDelete ? (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-stone-600 text-center">确认删除此会话？此操作不可恢复。</p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 hover:bg-stone-50 active:scale-[0.98]"
                onClick={() => setConfirmingDelete(false)}
              >
                取消
              </button>
              <button
                type="button"
                disabled={isDeleting}
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-100 active:scale-[0.98] disabled:opacity-50"
                onClick={() => void handleDelete()}
              >
                {isDeleting ? "删除中..." : "确认删除"}
              </button>
            </div>
            {deleteError ? <p className="text-xs text-red-600">{deleteError}</p> : null}
          </div>
        ) : (
          <button
            type="button"
            className="flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-600 transition-all duration-150 hover:border-red-300 hover:bg-red-100 active:scale-[0.98]"
            onClick={() => setConfirmingDelete(true)}
          >
            <Trash2 className="h-3.5 w-3.5" />
            删除当前会话
          </button>
        )}
      </div>
    </aside>
  );
}
