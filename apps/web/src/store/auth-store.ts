"use client";

import { create } from "zustand";
import { createJSONStorage, persist, StateStorage } from "zustand/middleware";

import type { User } from "../lib/types";


interface AuthState {
  accessToken: string | null;
  isAuthenticated: boolean;
  user: User | null;
  setAuth: (payload: { accessToken: string; user: User }) => void;
  clearAuth: () => void;
}


const noopStorage: StateStorage = {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
};

const storage = createJSONStorage(() =>
  typeof window === "undefined" ? noopStorage : window.localStorage,
);


export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      isAuthenticated: false,
      user: null,
      setAuth: ({ accessToken, user }) =>
        set({
          accessToken,
          isAuthenticated: true,
          user,
        }),
      clearAuth: () =>
        set({
          accessToken: null,
          isAuthenticated: false,
          user: null,
        }),
    }),
    {
      name: "ai-cofounder-auth",
      storage,
      partialize: (state) => ({
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
        user: state.user,
      }),
    },
  ),
);
