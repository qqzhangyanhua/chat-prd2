"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { login, register, SCHEMA_OUTDATED_DETAIL } from "../../lib/api";
import { getRecoveryActionFromError, resolveRecoveryAction } from "../../lib/recovery-action";
import { useSchemaGate } from "../../hooks/use-schema-gate";
import type { AuthMode } from "../../lib/types";
import { useAuthStore } from "../../store/auth-store";
import { SchemaOutdatedNotice } from "../workspace/schema-outdated-notice";
import { WorkspaceErrorNotice } from "../workspace/workspace-error-notice";


interface AuthFormProps {
  mode: AuthMode;
}


export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorCause, setErrorCause] = useState<unknown>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { schemaHealth, isCheckingSchema, checkSchemaGate, clearSchemaHealth } = useSchemaGate();
  const schemaRecoveryAction = resolveRecoveryAction(schemaHealth?.error?.recovery_action);
  const errorRecoveryAction = resolveRecoveryAction(getRecoveryActionFromError(errorCause), {
    onLogin: () => {
      router.push("/login");
    },
  });

  const titleLabelCn = mode === "login" ? "登录你的账号" : "创建你的账号";
  const subtitleLabelCn = mode === "login" ? "登录以继续使用 AI Co-founder" : "注册以继续使用 AI Co-founder";
  const submitLabel = "Continue";
  const submitAction = mode === "login" ? login : register;
  const switchHref = mode === "login" ? "/register" : "/login";
  const switchLabel = mode === "login" ? "Don't have an account? Sign up" : "Already have an account? Log in";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorCause(null);
    setErrorMessage(null);
    clearSchemaHealth();

    try {
      const response = await submitAction(email, password);
      setAuth({
        accessToken: response.access_token,
        user: response.user,
      });

      await checkSchemaGate({
        onReady: () => {
          router.push("/workspace");
        },
        onCheckFailed: () => {
          router.push("/workspace");
        },
      });
    } catch (error) {
      setErrorCause(error);
      setErrorMessage(
        error instanceof Error ? error.message : "认证请求失败",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSchemaRetry() {
    setErrorCause(null);
    setErrorMessage(null);

    try {
      await checkSchemaGate({
        onReady: () => {
          router.push("/workspace");
        },
      });
    } catch (error) {
      setErrorCause(error);
      setErrorMessage(error instanceof Error ? error.message : "健康检查失败，请稍后重试");
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[380px] flex-col items-center rounded-2xl border border-white/10 bg-brand-dark p-8 shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
      <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-full bg-brand-darker text-brand-primary ring-1 ring-white/10">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" strokeLinejoin="round"/>
        </svg>
      </div>

      <h2 className="mb-2 text-xl font-medium text-content-light">{titleLabelCn}</h2>
      <p className="mb-8 text-sm text-content-muted">{subtitleLabelCn}</p>

      <form className="flex w-full flex-col gap-4" onSubmit={handleSubmit}>
        <div className="flex flex-col gap-4">
          <input
            autoComplete="email"
            className="w-full rounded-lg border border-white/5 bg-brand-darker px-4 py-3 text-sm text-content-light placeholder-content-muted outline-none transition-all hover:border-white/10 focus:border-white/20 focus:ring-2 focus:ring-brand-primary/20"
            name="email"
            placeholder="Business email*"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />

          <input
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className="w-full rounded-lg border border-white/5 bg-brand-darker px-4 py-3 text-sm text-content-light placeholder-content-muted outline-none transition-all hover:border-white/10 focus:border-white/20 focus:ring-2 focus:ring-brand-primary/20"
            name="password"
            placeholder="Password*"
            type="password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        {errorMessage ? (
          <WorkspaceErrorNotice
            actionLabel={errorRecoveryAction?.onAction ? errorRecoveryAction.label : undefined}
            className="border-red-500/20 bg-red-500/10 text-red-400"
            message={errorMessage}
            onAction={errorRecoveryAction?.onAction}
          />
        ) : null}

        {schemaHealth?.schema === "outdated" ? (
          <SchemaOutdatedNotice
            actionLabel="重新检测"
            actionPending={isCheckingSchema}
            command={schemaRecoveryAction?.type === "run_migration" ? schemaRecoveryAction.target ?? undefined : undefined}
            detail={schemaHealth.detail ?? SCHEMA_OUTDATED_DETAIL}
            missingTables={schemaHealth.missing_tables}
            onAction={handleSchemaRetry}
          />
        ) : null}

        <button
          className="mt-2 flex w-full items-center justify-center rounded-[100px] bg-white/10 px-4 py-3 text-sm font-medium text-content-light transition-all hover:bg-white/20 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-4 w-4 animate-spin text-white/50" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" fill="currentColor" />
              </svg>
              提交中...
            </span>
          ) : submitLabel}
        </button>

        <div className="mt-4 mb-2 text-center">
          <Link
            className="text-xs text-content-muted transition-colors hover:text-content-light"
            href={switchHref}
          >
            {switchLabel}
          </Link>
        </div>

        <div className="my-2 flex items-center gap-3">
          <div className="h-[1px] flex-1 bg-white/5"></div>
          <span className="text-[10px] uppercase text-content-muted/60">OR</span>
          <div className="h-[1px] flex-1 bg-white/5"></div>
        </div>

        <div className="flex flex-col gap-3">
          <button type="button" className="flex w-full items-center justify-center gap-3 rounded-[100px] border border-white/10 bg-transparent px-4 py-3 text-sm font-medium text-content-light transition-all hover:bg-white/5 active:scale-[0.98]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>
          <button type="button" className="flex w-full items-center justify-center gap-3 rounded-[100px] border border-white/10 bg-transparent px-4 py-3 text-sm font-medium text-content-light transition-all hover:bg-white/5 active:scale-[0.98]">
            <svg width="16" height="16" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
              <rect x="1" y="1" width="9" height="9" fill="#F25022"/>
              <rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>
              <rect x="1" y="11" width="9" height="9" fill="#00A4EF"/>
              <rect x="11" y="11" width="9" height="9" fill="#FFB900"/>
            </svg>
            Continue with Microsoft
          </button>
        </div>
      </form>
    </div>
  );
}
