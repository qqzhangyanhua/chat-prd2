"use client";

import { create } from "zustand";

export type ToastTone = "info" | "success" | "error";

export interface ToastStateItem {
  id: string;
  message: string;
  tone: ToastTone;
}

interface ToastState {
  lastShownAt: number;
  lastSignature: string | null;
  toast: ToastStateItem | null;
  showToast: (payload: { id?: string; message: string; tone: ToastTone }) => string;
  clearToast: () => void;
}

const DEDUPE_WINDOW_MS = 1500;

export const useToastStore = create<ToastState>()((set, get) => ({
  lastShownAt: 0,
  lastSignature: null,
  toast: null,
  showToast: ({ id, message, tone }) => {
    const now = Date.now();
    const signature = `${tone}:${message}`;
    const current = get().toast;

    if (
      get().lastSignature === signature &&
      now - get().lastShownAt < DEDUPE_WINDOW_MS &&
      current
    ) {
      return current.id;
    }

    const nextId = id ?? `toast-${now}`;
    set({
      lastShownAt: now,
      lastSignature: signature,
      toast: {
        id: nextId,
        message,
        tone,
      },
    });
    return nextId;
  },
  clearToast: () =>
    set({
      toast: null,
    }),
}));
