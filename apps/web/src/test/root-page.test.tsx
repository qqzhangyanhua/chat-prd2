import { describe, expect, it, vi } from "vitest";

import HomePage from "../app/page";

const redirectMock = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => redirectMock(...args),
}));

describe("HomePage", () => {
  it("redirects root requests to the workspace entry", () => {
    HomePage();

    expect(redirectMock).toHaveBeenCalledWith("/workspace");
  });
});
