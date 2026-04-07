"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getHealthStatus, SCHEMA_OUTDATED_DETAIL } from "../../lib/api";
import type { HealthStatusResponse } from "../../lib/types";
import { useAuthStore } from "../../store/auth-store";
import { SchemaOutdatedNotice } from "../workspace/schema-outdated-notice";

export function HomeAuthRedirect() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [schemaHealth, setSchemaHealth] = useState<HealthStatusResponse | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      setSchemaHealth(null);
      return;
    }

    let cancelled = false;

    void getHealthStatus()
      .then((health) => {
        if (cancelled) {
          return;
        }

        if (health.schema === "outdated") {
          setSchemaHealth(health);
          return;
        }

        router.replace("/workspace");
      })
      .catch(() => {
        if (!cancelled) {
          router.replace("/workspace");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, router]);

  if (!isAuthenticated || schemaHealth?.schema !== "outdated") {
    return null;
  }

  return (
    <div className="mx-auto max-w-[1200px] px-6 pt-6">
      <SchemaOutdatedNotice
        detail={schemaHealth.detail ?? SCHEMA_OUTDATED_DETAIL}
        missingTables={schemaHealth.missing_tables}
      />
    </div>
  );
}
