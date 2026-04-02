"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { login, register } from "../../lib/api";
import type { AuthMode } from "../../lib/types";
import { useAuthStore } from "../../store/auth-store";


interface AuthFormProps {
  mode: AuthMode;
}


export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submitLabel = mode === "login" ? "登录" : "注册";
  const submitAction = mode === "login" ? login : register;
  const switchHref = mode === "login" ? "/register" : "/login";
  const switchLabel =
    mode === "login" ? "没有账号？去注册" : "已有账号？去登录";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await submitAction(email, password);
      setAuth({
        accessToken: response.access_token,
        user: response.user,
      });
      router.push("/workspace");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "认证请求失败",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form
      className="mx-auto flex w-full max-w-md flex-col gap-4 rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm"
      onSubmit={handleSubmit}
    >
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-neutral-950">{submitLabel}</h1>
        <p className="text-sm text-neutral-600">
          用邮箱和密码进入 AI Co-founder 工作台。
        </p>
      </div>

      <label className="flex flex-col gap-2 text-sm font-medium text-neutral-800">
        邮箱
        <input
          className="rounded-xl border border-neutral-300 px-4 py-3 text-sm outline-none transition focus:border-neutral-950"
          name="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </label>

      <label className="flex flex-col gap-2 text-sm font-medium text-neutral-800">
        密码
        <input
          className="rounded-xl border border-neutral-300 px-4 py-3 text-sm outline-none transition focus:border-neutral-950"
          name="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </label>

      {errorMessage ? (
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </p>
      ) : null}

      <button
        className="rounded-xl bg-neutral-950 px-4 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-neutral-500"
        disabled={isSubmitting}
        type="submit"
      >
        {isSubmitting ? "提交中..." : submitLabel}
      </button>

      <Link className="text-sm text-neutral-600 underline-offset-4 hover:underline" href={switchHref}>
        {switchLabel}
      </Link>
    </form>
  );
}
