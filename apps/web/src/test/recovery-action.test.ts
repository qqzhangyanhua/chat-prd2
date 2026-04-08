import { describe, expect, it, vi } from "vitest";

import { getRecoveryActionFromError, resolveRecoveryAction } from "../lib/recovery-action";

describe("recovery action helpers", () => {
  it("extracts recovery action from api-like errors", () => {
    const error = Object.assign(new Error("会话快照缺失"), {
      code: "SESSION_SNAPSHOT_MISSING",
      recoveryAction: {
        type: "reload_session",
        label: "重新加载会话",
        target: null,
      },
    });

    expect(getRecoveryActionFromError(error)).toEqual({
      type: "reload_session",
      label: "重新加载会话",
      target: null,
    });
  });

  it("resolves workspace navigation and retry style actions into callable handlers", () => {
    const onOpenWorkspaceHome = vi.fn();
    const onReloadSession = vi.fn();

    const openWorkspaceAction = resolveRecoveryAction(
      {
        type: "open_workspace_home",
        label: "返回工作台首页",
        target: "/workspace",
      },
      { onOpenWorkspaceHome },
    );
    const reloadAction = resolveRecoveryAction(
      {
        type: "reload_session",
        label: "重新加载会话",
        target: null,
      },
      { onReloadSession },
    );

    openWorkspaceAction?.onAction?.();
    reloadAction?.onAction?.();

    expect(openWorkspaceAction?.label).toBe("返回工作台首页");
    expect(reloadAction?.label).toBe("重新加载会话");
    expect(onOpenWorkspaceHome).toHaveBeenCalledTimes(1);
    expect(onReloadSession).toHaveBeenCalledTimes(1);
  });
});
