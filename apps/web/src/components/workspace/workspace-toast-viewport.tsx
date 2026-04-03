"use client";

import { useEffect } from "react";

import { useToastStore } from "../../store/toast-store";

const toneStyles = {
  info: "border-amber-200 bg-amber-50 text-amber-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  error: "border-red-200 bg-red-50 text-red-900",
} as const;

export function WorkspaceToastViewport() {
  const toast = useToastStore((state) => state.toast);
  const clearToast = useToastStore((state) => state.clearToast);

  useEffect(() => {
    if (!toast || toast.tone === "info") {
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
        className={`min-w-[240px] max-w-sm rounded-2xl border px-4 py-3 text-sm font-medium shadow-lg backdrop-blur ${toneStyles[toast.tone]}`}
        role="status"
      >
        {toast.message}
      </div>
    </div>
  );
}
