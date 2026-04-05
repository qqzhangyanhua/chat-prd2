"use client";

import { useEffect } from "react";

import { useToastStore } from "../../store/toast-store";

const toneStyles = {
  info: "border-amber-200/80 bg-amber-50 text-amber-900 shadow-amber-100",
  success: "border-emerald-200/80 bg-emerald-50 text-emerald-900 shadow-emerald-100",
  error: "border-red-200/80 bg-red-50 text-red-900 shadow-red-100",
} as const;

export function WorkspaceToastViewport() {
  const toast = useToastStore((state) => state.toast);
  const clearToast = useToastStore((state) => state.clearToast);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = window.setTimeout(() => {
      clearToast();
    }, 2400);

    return () => {
      window.clearTimeout(timer);
    };
  }, [clearToast, toast]);

  if (!toast) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed inset-x-4 top-4 z-50 flex justify-center sm:inset-x-auto sm:right-6 sm:top-6">
      <div
        aria-atomic="true"
        aria-live="polite"
        className={`min-w-[240px] max-w-sm rounded-xl border px-4 py-3 text-sm font-medium shadow-lg shadow-stone-200/60 backdrop-blur-sm ${toneStyles[toast.tone]}`}
        role="status"
      >
        {toast.message}
      </div>
    </div>
  );
}
