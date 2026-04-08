"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SCHEMA_OUTDATED_DETAIL } from "../../lib/api";
import { resolveRecoveryAction } from "../../lib/recovery-action";
import { useSchemaGate } from "../../hooks/use-schema-gate";
import { useAuthStore } from "../../store/auth-store";
import { SchemaOutdatedNotice } from "../workspace/schema-outdated-notice";

export function HomeAuthRedirect() {
  const { replace } = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [autoProbeEnabled, setAutoProbeEnabled] = useState(true);
  const { schemaHealth, isCheckingSchema, checkSchemaGate, clearSchemaHealth } = useSchemaGate();
  const schemaRecoveryAction = resolveRecoveryAction(schemaHealth?.error?.recovery_action);

  useEffect(() => {
    if (!isAuthenticated) {
      setAutoProbeEnabled(true);
      clearSchemaHealth();
      return;
    }

    if (!autoProbeEnabled || schemaHealth?.schema === "outdated") {
      return;
    }

    let cancelled = false;

    void checkSchemaGate({
      onReady: () => {
        if (!cancelled) {
          replace("/workspace");
        }
      },
      onCheckFailed: () => {
        if (!cancelled) {
          replace("/workspace");
        }
      },
    }).then((result) => {
      if (!cancelled && result === "outdated") {
        setAutoProbeEnabled(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [autoProbeEnabled, checkSchemaGate, clearSchemaHealth, isAuthenticated, replace, schemaHealth]);

  async function handleSchemaRetry() {
    await checkSchemaGate({
      onReady: () => {
        replace("/workspace");
      },
    });
  }

  if (!isAuthenticated || schemaHealth?.schema !== "outdated") {
    return null;
  }

  return (
    <div className="mx-auto max-w-[1200px] px-6 pt-6">
      <SchemaOutdatedNotice
        actionLabel="重新检测"
        actionPending={isCheckingSchema}
        command={schemaRecoveryAction?.type === "run_migration" ? schemaRecoveryAction.target ?? undefined : undefined}
        detail={schemaHealth.detail ?? SCHEMA_OUTDATED_DETAIL}
        missingTables={schemaHealth.missing_tables}
        onAction={handleSchemaRetry}
      />
    </div>
  );
}
