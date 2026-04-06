"use client";

import { useEffect, useState } from "react";
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
          user: {
            ...user,
            is_admin: user.is_admin ?? false,
          },
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

/**
 * Whether the auth store has finished hydrating from localStorage.
 * Guards against premature redirect during SSR -> client hydration.
 */
export function useAuthHydrated(): boolean {
  // Lazy initializer: if the store is already hydrated (e.g. after first render
  // or hot reload), skip the extra re-render cycle caused by useState(false).
  const [hydrated, setHydrated] = useState(() => useAuthStore.persist.hasHydrated());

  useEffect(() => {
    // Guard: already hydrated during initialization, nothing to subscribe to.
    if (useAuthStore.persist.hasHydrated()) {
      setHydrated(true);
      return;
    }
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      setHydrated(true);
    });
    return unsub;
  }, []);

  return hydrated;
}
