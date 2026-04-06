"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore, useAuthHydrated } from "../store/auth-store";

export function useAuthGuard(): { hydrated: boolean } {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hydrated = useAuthHydrated();

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.push("/login");
    }
  }, [hydrated, isAuthenticated, router]);

  return { hydrated };
}
