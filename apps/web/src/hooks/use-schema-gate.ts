"use client";

import { useCallback, useState } from "react";

import { getHealthStatus, SCHEMA_OUTDATED_DETAIL } from "../lib/api";
import type { HealthStatusResponse } from "../lib/types";

type SchemaGateResult = "ready" | "outdated" | "error";

interface SchemaGateOptions {
  onCheckFailed?: (error: unknown) => void | Promise<void>;
  onReady?: () => void | Promise<void>;
}

function isSchemaOutdatedError(error: unknown): boolean {
  if (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as { code?: unknown }).code === "SCHEMA_OUTDATED"
  ) {
    return true;
  }

  if (
    typeof error === "object" &&
    error !== null &&
    "message" in error &&
    (error as { message?: unknown }).message === SCHEMA_OUTDATED_DETAIL
  ) {
    return true;
  }

  return error === SCHEMA_OUTDATED_DETAIL;
}

export function useSchemaGate() {
  const [schemaHealth, setSchemaHealth] = useState<HealthStatusResponse | null>(null);
  const [isCheckingSchema, setIsCheckingSchema] = useState(false);

  const clearSchemaHealth = useCallback(() => {
    setSchemaHealth(null);
  }, []);

  const checkSchemaGate = useCallback(async (options: SchemaGateOptions = {}): Promise<SchemaGateResult> => {
    const { onCheckFailed, onReady } = options;
    setIsCheckingSchema(true);

    try {
      const health = await getHealthStatus();

      if (health.schema === "outdated") {
        setSchemaHealth(health);
        return "outdated";
      }

      setSchemaHealth(null);
      await onReady?.();
      return "ready";
    } catch (error) {
      if (onCheckFailed) {
        await onCheckFailed(error);
        return "error";
      }

      throw error;
    } finally {
      setIsCheckingSchema(false);
    }
  }, []);

  const syncSchemaFromError = useCallback(async (error: unknown): Promise<HealthStatusResponse | null> => {
    if (!isSchemaOutdatedError(error)) {
      setSchemaHealth(null);
      return null;
    }

    setIsCheckingSchema(true);

    try {
      const health = await getHealthStatus();

      if (health.schema === "outdated") {
        setSchemaHealth(health);
        return health;
      }

      setSchemaHealth(null);
      return null;
    } catch {
      setSchemaHealth(null);
      return null;
    } finally {
      setIsCheckingSchema(false);
    }
  }, []);

  const syncSchemaFromErrorMessage = useCallback(async (message: string): Promise<HealthStatusResponse | null> => {
    return syncSchemaFromError(message);
  }, [syncSchemaFromError]);

  return {
    checkSchemaGate,
    clearSchemaHealth,
    isCheckingSchema,
    isSchemaOutdated: schemaHealth?.schema === "outdated",
    schemaHealth,
    syncSchemaFromError,
    syncSchemaFromErrorMessage,
  };
}
