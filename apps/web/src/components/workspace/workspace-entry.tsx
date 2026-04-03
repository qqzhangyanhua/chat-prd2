"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { createSession, listSessions } from "../../lib/api";
import type { SessionResponse } from "../../lib/types";
import { useAuthStore } from "../../store/auth-store";


export function WorkspaceEntry() {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadSessions() {
      try {
        const response = await listSessions(accessToken);
        if (!cancelled) {
          if (response.sessions.length > 0) {
            router.push(`/workspace/${response.sessions[0].id}`);
            return;
          }
          setSessions(response.sessions);
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
  }, [accessToken, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await createSession(
        {
          title,
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

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.16),_transparent_30%),linear-gradient(180deg,_#f7f3ea_0%,_#f5f5f4_100%)] px-4 py-6 md:px-6">
      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[minmax(0,1.2fr)_380px]">
        <section className="rounded-[32px] border border-stone-200 bg-white/90 p-6 shadow-sm md:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-stone-500">
            AI Co-founder
          </p>
          <h1 className="mt-3 text-3xl font-semibold text-stone-950">开始一个新会话</h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
            输入一个想法，系统会持续追问、澄清和推动决策，并把过程沉淀成可执行的 PRD。
          </p>

          <form className="mt-8 grid gap-5" onSubmit={handleSubmit}>
            <label className="grid gap-2 text-sm font-medium text-stone-900">
              会话标题
              <input
                className="rounded-2xl border border-stone-300 bg-stone-50 px-4 py-3 outline-none transition focus:border-stone-900"
                name="title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-stone-900">
              初始想法
              <textarea
                className="min-h-40 rounded-3xl border border-stone-300 bg-stone-50 px-4 py-4 outline-none transition focus:border-stone-900"
                name="initial_idea"
                value={idea}
                onChange={(event) => setIdea(event.target.value)}
              />
            </label>

            {errorMessage ? (
              <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {errorMessage}
              </p>
            ) : null}

            <button
              className="w-fit rounded-2xl bg-stone-950 px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-stone-400"
              disabled={isSubmitting}
              type="submit"
            >
              {isSubmitting ? "创建中..." : "创建并进入工作台"}
            </button>
          </form>
        </section>

        <aside className="rounded-[32px] border border-stone-200 bg-stone-50 p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-stone-500">
            Recent Sessions
          </p>
          <h2 className="mt-3 text-2xl font-semibold text-stone-950">继续已有项目</h2>
          <div className="mt-6 grid gap-3">
            {sessions.length > 0 ? (
              sessions.map((session) => (
                <article
                  key={session.id}
                  className="rounded-3xl border border-stone-200 bg-white p-4"
                >
                  <p className="text-sm font-semibold text-stone-950">{session.title}</p>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-stone-600">
                    {session.initial_idea}
                  </p>
                  <button
                    className="mt-4 rounded-2xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-900"
                    onClick={() => router.push(`/workspace/${session.id}`)}
                    type="button"
                  >
                    进入已有项目
                  </button>
                </article>
              ))
            ) : (
              <div className="rounded-3xl border border-dashed border-stone-300 bg-white px-4 py-6 text-sm leading-7 text-stone-600">
                还没有会话。先创建一个项目，让智能体开始帮你收敛想法。
              </div>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
