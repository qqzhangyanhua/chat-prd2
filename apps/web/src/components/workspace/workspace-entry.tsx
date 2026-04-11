"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Bot, LayoutGrid, MessageSquare } from "lucide-react";

import { createSession, listSessions, SCHEMA_OUTDATED_DETAIL } from "../../lib/api";
import { getRecoveryActionFromError, resolveRecoveryAction } from "../../lib/recovery-action";
import { useSchemaGate } from "../../hooks/use-schema-gate";
import { storeNewSessionDraft } from "../../lib/new-session-draft";
import { useAuthStore } from "../../store/auth-store";
import { useAuthGuard } from "../../hooks/use-auth-guard";
import { BrandIcon } from "./brand-icon";
import { SchemaOutdatedNotice } from "./schema-outdated-notice";
import { SectionLabel } from "./section-label";
import { Spinner } from "./spinner";
import { WorkspaceErrorNotice } from "./workspace-error-notice";
import { WorkspaceLayout } from "./workspace-layout";

const TEMPLATES: { label: string; text: string }[] = [
  { label: "Product Discovery", text: "我有一个产品想法，想通过对话挖掘用户需求和核心问题。" },
  { label: "Feature Planning", text: "我需要为现有产品规划新功能，梳理优先级和实现路径。" },
  { label: "MVP Scope", text: "我想确定产品的 MVP 范围，找出最小可行闭环。" },
];

interface WorkspaceEntryProps {
  autoRedirectToLatest?: boolean;
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function WorkspaceEntry({ autoRedirectToLatest = true }: WorkspaceEntryProps) {
  const { hydrated } = useAuthGuard();
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const [errorCause, setErrorCause] = useState<unknown>(null);
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCheckingSessions, setIsCheckingSessions] = useState(true);
  const { schemaHealth, clearSchemaHealth, syncSchemaFromError } = useSchemaGate();
  const schemaRecoveryAction = resolveRecoveryAction(schemaHealth?.error?.recovery_action);
  const errorRecoveryAction = resolveRecoveryAction(getRecoveryActionFromError(errorCause), {
    onLogin: () => {
      router.push("/login");
    },
    onOpenWorkspaceHome: () => {
      router.push("/workspace/home");
    },
  });

  useEffect(() => {
    if (!hydrated) return;

    if (!autoRedirectToLatest) {
      setIsCheckingSessions(false);
      return;
    }

    let cancelled = false;

    async function loadSessions() {
      try {
        const response = await listSessions(accessToken);
        if (cancelled) return;
        clearSchemaHealth();
        if (response.sessions.length > 0) {
          const latest = response.sessions.reduce((best, s) =>
            new Date(best.updated_at) > new Date(s.updated_at) ? best : s,
          );
          router.push(`/workspace?session=${latest.id}`);
          return;
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "加载会话失败";
          setErrorCause(error);
          setErrorMessage(message);
          await syncSchemaFromError(error);
        }
      } finally {
        if (!cancelled) setIsCheckingSessions(false);
      }
    }

    void loadSessions();
    return () => { cancelled = true; };
  }, [hydrated, accessToken, autoRedirectToLatest, router, clearSchemaHealth, syncSchemaFromError]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorCause(null);
    setErrorMessage(null);
    clearSchemaHealth();
    try {
      const trimmedIdea = idea.trim();
      const response = await createSession(
        { title: title || "未命名会话", initial_idea: trimmedIdea },
        accessToken,
      );
      storeNewSessionDraft(response.session.id, trimmedIdea);
      router.push(`/workspace?session=${response.session.id}`);
    } catch (error) {
      setErrorCause(error);
      setErrorMessage(error instanceof Error ? error.message : "创建会话失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  const greeting = getGreeting();
  const email = user?.email ?? "用户";

  return (
    <WorkspaceLayout>
      <section className="flex flex-1 flex-col justify-center overflow-y-auto">
        <div className="mx-auto flex w-full max-w-[760px] flex-col px-4">
          <div className="mb-8 flex items-center justify-center gap-4">
            <BrandIcon size="md" />
            <h1 className="font-serif text-3xl tracking-wide text-stone-950 sm:text-4xl">
              {greeting}, {email.split("@")[0]}
            </h1>
          </div>

          {schemaHealth?.schema === "outdated" ? (
            <div className="mb-6">
              <SchemaOutdatedNotice
                command={schemaRecoveryAction?.type === "run_migration" ? schemaRecoveryAction.target ?? undefined : undefined}
                detail={schemaHealth.detail ?? SCHEMA_OUTDATED_DETAIL}
                missingTables={schemaHealth.missing_tables}
              />
            </div>
          ) : null}

          {isCheckingSessions ? (
            <div className="flex min-h-[280px] items-center justify-center rounded-2xl border border-stone-200/80 bg-white/90 p-5 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
              <div className="flex items-center gap-3 text-sm text-stone-500">
                <Spinner size="md" variant="dark" />
                正在检查最近会话...
              </div>
            </div>
          ) : (
            <>
              <div className="relative w-full rounded-2xl border border-stone-200/80 bg-white/90 p-5 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
                <form onSubmit={handleSubmit} className="flex flex-col">
                  <label className="block">
                    <SectionLabel className="mb-2.5 block">Describe your idea</SectionLabel>
                    <textarea
                      className="min-h-[120px] w-full resize-none rounded-xl border border-stone-200 bg-stone-50 px-4 py-3.5 text-sm leading-7 text-stone-800 outline-none transition-all duration-150 placeholder:text-stone-400 hover:border-stone-300 focus:border-stone-900 focus:bg-white focus:ring-2 focus:ring-stone-900/8"
                      placeholder="Tell me about your product idea, the problem you're solving, or what you want to build..."
                      value={idea}
                      onChange={(e) => setIdea(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          if (idea.trim() && !isSubmitting) e.currentTarget.form?.requestSubmit();
                        }
                      }}
                    />
                  </label>

                  {errorMessage ? (
                    <WorkspaceErrorNotice
                      actionLabel={errorRecoveryAction?.onAction ? errorRecoveryAction.label : undefined}
                      className="mt-3 border-red-200 bg-red-50 text-red-700"
                      message={errorMessage}
                      onAction={errorRecoveryAction?.onAction}
                    />
                  ) : null}

                  <div className="mt-4 flex items-center justify-between border-t border-stone-100 pt-4">
                    <input
                      type="text"
                      placeholder="Project name (optional)"
                      className="w-48 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-xs text-stone-900 outline-none transition-all duration-150 hover:border-stone-300 focus:border-stone-900 focus:bg-white focus:ring-2 focus:ring-stone-900/8"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                    <button
                      type="submit"
                      disabled={!idea.trim() || isSubmitting}
                      className="flex cursor-pointer items-center gap-2 rounded-xl bg-stone-950 px-4 py-2.5 text-sm font-semibold text-white transition-all duration-150 hover:bg-stone-800 active:scale-[0.97] disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-500"
                    >
                      {isSubmitting ? (
                        <>
                          <Spinner size="sm" variant="light" />
                          Starting...
                        </>
                      ) : (
                        <>
                          <ArrowRight className="h-3.5 w-3.5" />
                          Start Session
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>

              <div className="mt-6">
                <p className="mb-3 text-center text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400">
                  or start with a template
                </p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {TEMPLATES.map(({ label, text }) => (
                    <button
                      key={label}
                      type="button"
                      className="flex items-center gap-2 rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 transition-all hover:border-stone-300 hover:bg-stone-50 active:scale-[0.98]"
                      onClick={() => setIdea(text)}
                    >
                      {label === "Product Discovery" ? <MessageSquare className="h-3.5 w-3.5" /> : null}
                      {label === "Feature Planning" ? <Bot className="h-3.5 w-3.5" /> : null}
                      {label === "MVP Scope" ? <LayoutGrid className="h-3.5 w-3.5" /> : null}
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </section>
    </WorkspaceLayout>
  );
}
