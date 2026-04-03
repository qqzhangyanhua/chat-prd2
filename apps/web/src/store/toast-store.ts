"use client";

import { create } from "zustand";

export type ToastTone = "info" | "success" | "error";

export interface ToastStateItem {
  id: string;
  message: string;
  tone: ToastTone;
}

interface ToastState {
  toast: ToastStateItem | null;
  showToast: (payload: { id?: string; message: string; tone: ToastTone }) => string;
  clearToast: () => void;
}

export const useToastStore = create<ToastState>()((set) => ({
  toast: null,
  showToast: ({ id, message, tone }) => {
    const nextId = id ?? `toast-${Date.now()}`;
    set({
      toast: {
        id: nextId,
        message,
        tone,
      },
    });
    return nextId;
  },
  clearToast: () => set({ toast: null }),
}));
