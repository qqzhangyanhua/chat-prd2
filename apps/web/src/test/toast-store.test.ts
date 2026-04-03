import { beforeEach, describe, expect, it, vi } from "vitest";

import { useToastStore } from "../store/toast-store";

describe("toast store", () => {
  beforeEach(() => {
    useToastStore.getState().clearToast();
    vi.restoreAllMocks();
  });

  it("deduplicates the same toast message in a short time window", () => {
    vi.spyOn(Date, "now")
      .mockReturnValueOnce(1000)
      .mockReturnValueOnce(1200);

    const firstId = useToastStore.getState().showToast({
      message: "会话加载失败",
      tone: "error",
    });
    const secondId = useToastStore.getState().showToast({
      message: "会话加载失败",
      tone: "error",
    });

    expect(secondId).toBe(firstId);
    expect(useToastStore.getState().toast?.id).toBe(firstId);
    expect(useToastStore.getState().toast?.message).toBe("会话加载失败");
  });
});
