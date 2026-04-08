import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSchemaGate } from "../hooks/use-schema-gate";

const getHealthStatusMock = vi.fn();

vi.mock("../lib/api", () => ({
  getHealthStatus: (...args: unknown[]) => getHealthStatusMock(...args),
  SCHEMA_OUTDATED_DETAIL: "数据库结构版本过旧，请先执行 alembic upgrade head",
}));

describe("useSchemaGate", () => {
  beforeEach(() => {
    getHealthStatusMock.mockReset();
  });

  it("runs ready callback when schema is ready", async () => {
    getHealthStatusMock.mockResolvedValue({
      status: "ok",
      schema: "ready",
    });
    const onReady = vi.fn();

    const { result } = renderHook(() => useSchemaGate());

    await act(async () => {
      await result.current.checkSchemaGate({ onReady });
    });

    expect(onReady).toHaveBeenCalledTimes(1);
    expect(result.current.schemaHealth).toBeNull();
  });

  it("stores schema health when schema is outdated", async () => {
    getHealthStatusMock.mockResolvedValue({
      status: "degraded",
      schema: "outdated",
      detail: "数据库结构版本过旧，请先执行 alembic upgrade head",
      missing_tables: ["agent_turn_decisions"],
    });

    const { result } = renderHook(() => useSchemaGate());

    await act(async () => {
      await result.current.checkSchemaGate();
    });

    expect(result.current.schemaHealth?.schema).toBe("outdated");
    expect(result.current.schemaHealth?.missing_tables).toEqual(["agent_turn_decisions"]);
  });

  it("hydrates schema detail when the api error code indicates outdated schema", async () => {
    getHealthStatusMock.mockResolvedValue({
      status: "degraded",
      schema: "outdated",
      detail: "数据库结构版本过旧，请先执行 alembic upgrade head",
      missing_tables: ["assistant_reply_versions"],
    });

    const { result } = renderHook(() => useSchemaGate());

    await act(async () => {
      await result.current.syncSchemaFromError(new Error("普通加载失败"));
    });

    expect(getHealthStatusMock).not.toHaveBeenCalled();
    expect(result.current.schemaHealth).toBeNull();

    await act(async () => {
      await result.current.syncSchemaFromError({
        message: "数据库结构版本过旧，请先执行 alembic upgrade head",
        code: "SCHEMA_OUTDATED",
      });
    });

    await waitFor(() => {
      expect(getHealthStatusMock).toHaveBeenCalledTimes(1);
      expect(result.current.schemaHealth?.missing_tables).toEqual(["assistant_reply_versions"]);
    });
  });
});
