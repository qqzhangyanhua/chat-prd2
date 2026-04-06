"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Download,
  RotateCcw,
  Trash2,
  Check,
  Clock,
  Home,
  MoreVertical,
  LogOut,
} from "lucide-react";

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
import { useWorkspaceStore, workspaceStore } from "../../store/workspace-store";
import { BrandIcon } from "./brand-icon";

interface WorkspaceLeftNavProps {
  sessionId?: string;
}

type DateGroup = 'today' | 'yesterday' | 'thisWeek' | 'thisMonth' | 'older';

interface GroupedSessions {
  today: SessionResponse[];
  yesterday: SessionResponse[];
  thisWeek: SessionResponse[];
  thisMonth: SessionResponse[];
  older: SessionResponse[];
}

interface DateBoundaries {
  todayStart: Date;
  todayEnd: Date;
  yesterdayStart: Date;
  yesterdayEnd: Date;
  weekStart: Date;
  monthStart: Date;
}

function getDateBoundaries(): DateBoundaries {
  const now = new Date();
  
  // Today boundaries
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
  
  // Yesterday boundaries
  const yesterdayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 0, 0, 0, 0);
  const yesterdayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59, 999);
  
  // Week start (Monday) - excluding today if today is Monday
  const dayOfWeek = now.getDay(); // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
  const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // If Sunday, go back 6 days; otherwise go back (dayOfWeek - 1) days
  const weekStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - daysToMonday, 0, 0, 0, 0);
  
  // Month start
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0);
  
  return {
    todayStart,
    todayEnd,
    yesterdayStart,
    yesterdayEnd,
    weekStart,
    monthStart,
  };
}

function groupSessionsByDate(sessions: SessionResponse[]): GroupedSessions {
  const boundaries = getDateBoundaries();
  
  const grouped: GroupedSessions = {
    today: [],
    yesterday: [],
    thisWeek: [],
    thisMonth: [],
    older: [],
  };
  
  for (const session of sessions) {
    const updatedAt = new Date(session.updated_at);
    
    // Handle invalid dates by placing in "older" group
    if (Number.isNaN(updatedAt.getTime())) {
      grouped.older.push(session);
      continue;
    }
    
    const timestamp = updatedAt.getTime();
    
    // Check boundaries in order
    if (timestamp >= boundaries.todayStart.getTime() && timestamp <= boundaries.todayEnd.getTime()) {
      grouped.today.push(session);
    } else if (timestamp >= boundaries.yesterdayStart.getTime() && timestamp <= boundaries.yesterdayEnd.getTime()) {
      grouped.yesterday.push(session);
    } else if (timestamp >= boundaries.weekStart.getTime() && timestamp < boundaries.todayStart.getTime()) {
      // This week excludes today and yesterday
      if (timestamp < boundaries.yesterdayStart.getTime()) {
        grouped.thisWeek.push(session);
      } else {
        // This is yesterday, already handled above
        grouped.yesterday.push(session);
      }
    } else if (timestamp >= boundaries.monthStart.getTime() && timestamp < boundaries.weekStart.getTime()) {
      grouped.thisMonth.push(session);
    } else {
      grouped.older.push(session);
    }
  }
  
  // Sort sessions within each group by updated_at descending, then by id for stability
  const sortSessions = (a: SessionResponse, b: SessionResponse) => {
    const aTime = new Date(a.updated_at).getTime();
    const bTime = new Date(b.updated_at).getTime();
    if (aTime !== bTime) {
      return bTime - aTime; // Descending order (most recent first)
    }
    return a.id.localeCompare(b.id); // Stable sort by id
  };
  
  grouped.today.sort(sortSessions);
  grouped.yesterday.sort(sortSessions);
  grouped.thisWeek.sort(sortSessions);
  grouped.thisMonth.sort(sortSessions);
  grouped.older.sort(sortSessions);
  
  return grouped;
}

const GROUP_LABELS: Record<DateGroup, string> = {
  today: '今天',
  yesterday: '昨天',
  thisWeek: '本周',
  thisMonth: '本月',
  older: '更早',
};

interface GroupHeaderProps {
  groupKey: DateGroup;
  count: number;
  isFirst: boolean;
}

function GroupHeader({ groupKey, count, isFirst }: GroupHeaderProps) {
  const label = GROUP_LABELS[groupKey];
  const ariaLabel = `${label}, ${count} 个会话`;
  
  return (
    <div
      className={`text-[10px] uppercase font-semibold text-stone-400 tracking-[0.28em] mb-2 ${isFirst ? '' : 'mt-3'}`}
      aria-label={ariaLabel}
      role="heading"
      aria-level={2}
    >
      {label} ({count})
    </div>
  );
}

function formatRecentActivity(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  const diffMs = Math.max(Date.now() - date.getTime(), 0);
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  if (diffMinutes < 1) return "刚刚活跃";
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  return `${Math.floor(diffHours / 24)} 天前`;
}

export function WorkspaceLeftNav({ sessionId }: WorkspaceLeftNavProps) {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const showToast = useToastStore((state) => state.showToast);

  const [showUserMenu, setShowUserMenu] = useState(false);

  // Session-specific state — only active when sessionId is present
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [titleDraft, setTitleDraft] = useState("");
  const [isTitleDirty, setIsTitleDirty] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [isRecovering, setIsRecovering] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const hasMountedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    async function loadSessions() {
      try {
        const response = await listSessions(accessToken);
        if (!cancelled) setSessions(response.sessions);
      } catch {
        if (!cancelled) setSessions([]);
      }
    }
    void loadSessions();
    return () => { cancelled = true; };
  }, [accessToken, sessionId]);

  const activeSession = useMemo(
    () => (sessionId ? sessions.find((s) => s.id === sessionId) ?? null : null),
    [sessionId, sessions],
  );

  useEffect(() => {
    if (!isTitleDirty) setTitleDraft(activeSession?.title ?? "");
    setRenameError(null);
  }, [activeSession, isTitleDirty]);

  useEffect(() => {
    if (!hasMountedRef.current) { hasMountedRef.current = true; return; }
    setDeleteError(null);
    setIsDeleting(false);
    setConfirmingDelete(false);
    setIsRecovering(false);
    setIsExporting(false);
    setIsRenaming(false);
    setIsTitleDirty(false);
    setTitleDraft("");
  }, [sessionId]);

  const groupedSessions = useMemo(() => groupSessionsByDate(sessions), [sessions]);
  const groupOrder: DateGroup[] = ['today', 'yesterday', 'thisWeek', 'thisMonth', 'older'];

  async function handleRename() {
    if (isRenaming || !sessionId) return;
    const normalizedTitle = titleDraft.trim();
    if (!normalizedTitle) { setRenameError("会话标题不能为空"); return; }
    try {
      setRenameError(null);
      setIsRenaming(true);
      showToast({ id: `rename-session-${sessionId}`, message: "正在保存标题...", tone: "info" });
      const snapshot = await updateSession(sessionId, { title: normalizedTitle }, accessToken);
      setTitleDraft(snapshot.session.title);
      setIsTitleDirty(false);
      setSessions((current) =>
        current.map((s) => (s.id === sessionId ? { ...s, ...snapshot.session } : s)),
      );
      showToast({ id: `rename-session-${sessionId}`, message: "标题已更新", tone: "success" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "重命名失败，请稍后再试";
      setRenameError(message);
      showToast({ id: `rename-session-${sessionId}`, message, tone: "error" });
    } finally {
      setIsRenaming(false);
    }
  }

  async function handleRecover() {
    if (isRecovering || !sessionId) return;
    try {
      setIsRecovering(true);
      showToast({ id: `recover-session-${sessionId}`, message: "正在恢复会话...", tone: "info" });
      const snapshot = await getSession(sessionId, accessToken);
      workspaceStore.getState().hydrateSession(snapshot);
      showToast({ id: `recover-session-${sessionId}`, message: "会话已恢复", tone: "success" });
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

  async function handleExport() {
    if (isExporting || !sessionId) return;
    try {
      setIsExporting(true);
      showToast({ id: `export-session-${sessionId}`, message: "正在导出 PRD...", tone: "info" });
      const exported = await exportSession(sessionId, accessToken);
      if (typeof URL.createObjectURL === "function") {
        const blob = new Blob([exported.content], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = exported.file_name;
        link.click();
        URL.revokeObjectURL(url);
      }
      showToast({ id: `export-session-${sessionId}`, message: "PRD 已导出", tone: "success" });
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

  async function handleDelete() {
    if (isDeleting || !sessionId) return;
    try {
      setDeleteError(null);
      setIsDeleting(true);
      showToast({ id: `delete-session-${sessionId}`, message: "正在删除会话...", tone: "info" });
      await deleteSession(sessionId, accessToken);
      showToast({ id: `delete-session-${sessionId}`, message: "会话已删除", tone: "success" });
      router.push("/workspace");
    } catch (error) {
      const message = error instanceof Error ? error.message : "删除失败，请稍后再试";
      setDeleteError(message);
      setIsDeleting(false);
      showToast({ id: `delete-session-${sessionId}`, message, tone: "error" });
    }
  }

  const email = user?.email ?? "用户";

  const isCollapsed = useWorkspaceStore((state) => state.isLeftNavCollapsed);
  const setCollapsed = useWorkspaceStore((state) => state.setLeftNavCollapsed);

  if (isCollapsed) {
    return (
      <div className="flex flex-col items-center py-4 w-12 shrink-0">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-stone-500 hover:bg-stone-200/50 hover:text-stone-900 transition-colors"
          title="展开侧边栏"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <path d="M15 3v18" />
            <path d="m8 9 3 3-3 3" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <aside className="group relative flex h-full w-[260px] shrink-0 flex-col bg-transparent py-4 text-sm font-medium transition-all duration-300">
      {/* Collapse button positioned to top right of sidebar */}
      <button
        type="button"
        onClick={() => setCollapsed(true)}
        className="absolute right-0 top-4 flex h-6 w-6 items-center justify-center rounded bg-stone-100 text-stone-400 opacity-0 transition-all hover:bg-stone-200 hover:text-stone-600 focus:opacity-100 group-hover:opacity-100"
        title="收起侧边栏"
      >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <path d="M9 3v18" />
            <path d="m16 15-3-3 3-3" />
          </svg>
      </button>
      {/* Logo */}
      <div className="mb-6 shrink-0 flex items-center gap-2.5">
        <BrandIcon size="sm" />
        <span className="text-sm font-bold tracking-tight text-stone-950">AI Co-founder</span>
      </div>

      {/* Nav */}
      <nav className="mb-4 shrink-0 space-y-1">
        <button
          type="button"
          className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-semibold transition-all ${!sessionId ? "bg-stone-950 text-white" : "text-stone-600 hover:bg-stone-50 hover:text-stone-900"}`}
          onClick={() => router.push("/workspace")}
        >
          <Home className="h-3.5 w-3.5" />
          Home
        </button>
        <button
          type="button"
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-stone-600 transition-all hover:bg-stone-50 hover:text-stone-900"
          onClick={() => router.push("/workspace?new=1")}
        >
          <Plus className="h-3.5 w-3.5" />
          New Session
        </button>
      </nav>

      {/* Middle — session list (always visible) */}
      <div className="flex flex-1 min-h-0 flex-col overflow-y-auto">
        {groupOrder.map((groupKey, groupIndex) => {
          const groupSessions = groupedSessions[groupKey];
          if (groupSessions.length === 0) return null;
          
          return (
            <div key={groupKey}>
              <GroupHeader 
                groupKey={groupKey} 
                count={groupSessions.length}
                isFirst={groupIndex === 0 || groupOrder.slice(0, groupIndex).every(k => groupedSessions[k].length === 0)}
              />
              <div className="space-y-1.5">
                {groupSessions.map((session) => {
                  const isActive = session.id === sessionId;
                  const isDeletingThis = isActive && isDeleting;
                  return (
                    <button
                      key={session.id}
                      type="button"
                      aria-label={`打开会话 ${session.title}`}
                      disabled={isDeletingThis}
                      className={`cursor-pointer rounded-xl border px-3 py-3 text-left transition-all duration-150 ${
                        isActive
                          ? "border-stone-900 bg-stone-950 text-white"
                          : "border-stone-100 bg-white/60 text-stone-700 hover:border-stone-200 hover:bg-white"
                      } ${isDeletingThis ? "cursor-not-allowed opacity-60" : ""}`}
                      onClick={() => router.push(`/workspace?session=${session.id}`)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className={`truncate text-xs font-semibold ${isActive ? "text-white" : "text-stone-900"}`}>
                          {session.title}
                        </p>
                        {isDeletingThis ? <span className="shrink-0 text-[10px] text-red-400">删除中</span> : null}
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-stone-400">
                        {session.initial_idea}
                      </p>
                      <p className={`mt-1.5 text-[10px] ${isActive ? "text-stone-500" : "text-stone-400"}`}>
                        {formatRecentActivity(session.updated_at)}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Session controls — only when viewing a session */}
      {sessionId ? (
        <div className="mt-3 shrink-0 space-y-3 border-t border-stone-100 pt-3">
          {/* Active session info */}
          <div className="rounded-xl border border-stone-200 bg-stone-50 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400">Active Session</p>
            <p className="mt-1 truncate text-xs font-semibold text-stone-950">
              {activeSession?.title ?? sessionId}
            </p>
            {activeSession ? (
              <div className="mt-1 flex items-center gap-1.5 text-[10px] text-stone-400">
                <Clock className="h-3 w-3" />
                <span>{formatRecentActivity(activeSession.updated_at)}</span>
              </div>
            ) : null}
          </div>

          {/* Rename */}
          <div className="flex flex-col gap-1.5">
            <label className="flex flex-col gap-1 text-xs font-medium text-stone-700">
              重命名
              <input
                className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-xs text-stone-900 outline-none transition-all hover:border-stone-300 focus:border-stone-900 focus:bg-white focus:ring-2 focus:ring-stone-900/8"
                value={titleDraft}
                onChange={(e) => { setTitleDraft(e.target.value); setIsTitleDirty(true); }}
              />
            </label>
            <button
              type="button"
              disabled={isRenaming}
              className="flex items-center justify-center gap-1.5 rounded-lg bg-stone-950 px-3 py-2 text-xs font-semibold text-white transition-all hover:bg-stone-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-stone-300"
              onClick={() => void handleRename()}
            >
              <Check className="h-3.5 w-3.5" />
              {isRenaming ? "保存中..." : "保存标题"}
            </button>
            {renameError ? <p className="text-xs text-red-600">{renameError}</p> : null}
          </div>

          {/* Action buttons */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              disabled={isRecovering}
              className="flex items-center justify-center gap-1 rounded-lg border border-stone-200 bg-white px-2 py-2 text-xs font-medium text-stone-700 transition-all hover:bg-stone-50 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => void handleRecover()}
            >
              <RotateCcw className="h-3.5 w-3.5" />
              {isRecovering ? "恢复中..." : "恢复会话"}
            </button>
            <button
              type="button"
              disabled={isExporting}
              className="flex items-center justify-center gap-1 rounded-lg border border-stone-200 bg-white px-2 py-2 text-xs font-medium text-stone-700 transition-all hover:bg-stone-50 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => void handleExport()}
            >
              <Download className="h-3.5 w-3.5" />
              {isExporting ? "导出中..." : "导出 PRD"}
            </button>
          </div>

          {user?.is_admin ? (
            <button
              type="button"
              className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 transition-all hover:bg-stone-50 active:scale-[0.98]"
              onClick={() => router.push("/admin/models")}
            >
              模型管理
            </button>
          ) : null}

          {/* Delete zone */}
          {confirmingDelete ? (
            <div className="flex flex-col gap-2">
              <p className="text-center text-xs text-stone-600">确认删除此会话？此操作不可恢复。</p>
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
              className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-600 transition-all hover:bg-red-100 active:scale-[0.98]"
              onClick={() => setConfirmingDelete(true)}
            >
              <Trash2 className="h-3.5 w-3.5" />
              删除当前会话
            </button>
          )}
        </div>
      ) : null}

      {/* User card */}
      <div className={`shrink-0 ${sessionId ? "mt-3" : "mt-auto"}`}>
        <div className="relative flex items-center justify-between rounded-xl border border-stone-200 bg-stone-50 p-2.5 shadow-sm">
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-primary to-brand-accent text-xs font-bold text-white shadow-sm">
              {email.substring(0, 2).toUpperCase()}
            </div>
            <div className="flex flex-col overflow-hidden">
              <span className="truncate text-xs font-semibold text-stone-900">{email.split("@")[0]}</span>
              <span className="truncate text-[10px] text-stone-500">Personal</span>
            </div>
          </div>
          <button
            type="button"
            aria-label="more"
            className="shrink-0 p-1 text-stone-400 transition-colors hover:text-stone-600"
            onClick={() => setShowUserMenu((v) => !v)}
          >
            <MoreVertical className="h-4 w-4" />
          </button>
          {showUserMenu ? (
            <div className="absolute bottom-full right-0 z-10 mb-1 w-36 rounded-xl border border-stone-200 bg-white py-1 shadow-lg">
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-xs text-stone-700 hover:bg-stone-50"
                onClick={() => { clearAuth(); router.push("/login"); }}
              >
                <LogOut className="h-3.5 w-3.5" />
                退出登录
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
