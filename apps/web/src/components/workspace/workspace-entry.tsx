"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  ArrowRight,
  Home,
  Bot,
  LayoutGrid,
  Calendar,
  HelpCircle,
  Download,
  MoreVertical,
  MessageSquare
} from "lucide-react";

import { createSession, listSessions } from "../../lib/api";
import { useAuthStore } from "../../store/auth-store";
import { WorkspaceToastViewport } from "./workspace-toast-viewport";

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function WorkspaceEntry() {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadSessions() {
      try {
        const response = await listSessions(accessToken);
        if (!cancelled) {
          if (response.sessions.length > 0) {
            const latest = response.sessions.reduce((a, b) =>
              new Date(a.created_at) > new Date(b.created_at) ? a : b
            );
            router.push(`/workspace/${latest.id}`);
          }
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "加载会话失败");
        }
      }
    }

    void loadSessions();

    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await createSession(
        {
          title: title || "未命名会话",
          initial_idea: idea,
        },
        accessToken,
      );
      router.push(`/workspace/${response.session.id}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "创建会话失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  const greeting = getGreeting();
  const email = user?.email || "用户";

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.12),_transparent_28%),linear-gradient(180deg,_#f5f5f4_0%,_#fafaf9_48%,_#f5f5f4_100%)] px-4 py-4 md:px-6 md:py-6">
      <WorkspaceToastViewport />
      
      <div className="mx-auto flex max-w-[1600px] gap-4 h-[calc(100vh-2rem)] md:h-[calc(100vh-3rem)]">
        {/* Sidebar */}
        <aside className="flex w-[280px] flex-col justify-between rounded-2xl border border-stone-200/80 bg-white/90 p-4 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
        <div>
          {/* Logo */}
          <div className="mb-6 flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand-primary to-brand-accent text-white shadow-sm">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="text-sm font-bold tracking-tight text-stone-950">AI Co-founder</span>
          </div>

          {/* Navigation */}
          <nav className="space-y-1 mb-6">
            <button className="flex w-full items-center gap-2.5 rounded-lg bg-stone-950 px-3 py-2 text-xs font-semibold text-white transition-all">
              <Home className="h-3.5 w-3.5" />
              Home
            </button>
            <button className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-stone-600 transition-all hover:bg-stone-50 hover:text-stone-900">
              <Plus className="h-3.5 w-3.5" />
              New Session
            </button>
          </nav>

          <div className="space-y-4">
            <div>
              <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400">Quick Actions</p>
              <div className="space-y-0.5">
                <button className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-stone-600 transition-all hover:bg-stone-50 hover:text-stone-900">
                  <MessageSquare className="h-3.5 w-3.5" />
                  Product Discovery
                </button>
                <button className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-stone-600 transition-all hover:bg-stone-50 hover:text-stone-900">
                  <LayoutGrid className="h-3.5 w-3.5" />
                  Feature Planning
                </button>
                <button className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-stone-600 transition-all hover:bg-stone-50 hover:text-stone-900">
                  <Calendar className="h-3.5 w-3.5" />
                  Roadmap Review
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          
          <div className="flex items-center justify-between rounded-xl border border-stone-200 bg-stone-50 p-2.5 shadow-sm">
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-primary to-brand-accent text-xs font-bold text-white shadow-sm">
                {email.substring(0, 2).toUpperCase()}
              </div>
              <div className="flex flex-col overflow-hidden">
                <span className="truncate text-xs font-semibold text-stone-900">{email.split("@")[0]}</span>
                <span className="truncate text-[10px] text-stone-500">Personal</span>
              </div>
            </div>
            <button className="shrink-0 p-1 text-stone-400 hover:text-stone-600 transition-colors">
              <MoreVertical className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <section className="flex-1 flex flex-col justify-center overflow-y-auto">
        <div className="mx-auto w-full max-w-[760px] flex flex-col px-4">
          
          {/* Greeting */}
          <div className="mb-8 flex items-center justify-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-primary to-brand-accent text-white shadow-lg">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" strokeLinejoin="round"/>
              </svg>
            </div>
            <h1 className="font-serif text-3xl sm:text-4xl tracking-wide text-stone-950">
              {greeting}, {email.split("@")[0]}
            </h1>
          </div>

          {/* Input Box */}
          <div className="relative w-full rounded-2xl border border-stone-200/80 bg-white/90 p-5 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
            <form onSubmit={handleSubmit} className="flex flex-col">
              <label className="block">
                <span className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400 mb-2.5 block">
                  Describe your idea
                </span>
                <textarea
                  className="w-full resize-none rounded-xl border border-stone-200 bg-stone-50 px-4 py-3.5 text-sm leading-7 text-stone-800 placeholder:text-stone-400 outline-none transition-all duration-150 hover:border-stone-300 focus:border-stone-900 focus:bg-white focus:ring-2 focus:ring-stone-900/8 min-h-[120px]"
                  placeholder="Tell me about your product idea, the problem you're solving, or what you want to build..."
                  value={idea}
                  onChange={(e) => setIdea(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      if (idea.trim() && !isSubmitting) {
                        e.currentTarget.form?.requestSubmit();
                      }
                    }
                  }}
                />
              </label>
              
              {errorMessage && (
                <div className="mt-3 text-sm text-red-600 px-1">{errorMessage}</div>
              )}

              <div className="flex items-center justify-between mt-4 pt-4 border-t border-stone-100">
                <div className="flex items-center gap-3">
                  <input 
                    type="text" 
                    placeholder="Project name (optional)" 
                    className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-xs text-stone-900 outline-none transition-all duration-150 hover:border-stone-300 focus:border-stone-900 focus:bg-white focus:ring-2 focus:ring-stone-900/8 w-48"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </div>
                
                <button 
                  type="submit"
                  disabled={!idea.trim() || isSubmitting}
                  className="flex cursor-pointer items-center gap-2 rounded-xl bg-stone-950 px-4 py-2.5 text-sm font-semibold text-white transition-all duration-150 hover:bg-stone-800 active:scale-[0.97] disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-500"
                >
                  {isSubmitting ? (
                    <>
                      <div className="h-3.5 w-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
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

          {/* Quick Actions */}
          <div className="mt-6">
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400 mb-3 text-center">
              or start with a template
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2">
              <button className="flex items-center gap-2 rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 transition-all hover:border-stone-300 hover:bg-stone-50 active:scale-[0.98]">
                <MessageSquare className="h-3.5 w-3.5" /> Product Discovery
              </button>
              <button className="flex items-center gap-2 rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 transition-all hover:border-stone-300 hover:bg-stone-50 active:scale-[0.98]">
                <Bot className="h-3.5 w-3.5" /> Feature Planning
              </button>
              <button className="flex items-center gap-2 rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 transition-all hover:border-stone-300 hover:bg-stone-50 active:scale-[0.98]">
                <LayoutGrid className="h-3.5 w-3.5" /> MVP Scope
              </button>
            </div>
          </div>
          
        </div>
      </section>
      </div>
    </main>
  );
}
