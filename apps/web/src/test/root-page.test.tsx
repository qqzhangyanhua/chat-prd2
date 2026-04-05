import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "../app/page";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

describe("HomePage", () => {
  beforeEach(() => {
    replaceMock.mockReset();
  });

  it("renders the landing page hero when unauthenticated", () => {
    render(<HomePage />);

    expect(screen.getByText("AI 联合创始人")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "立即开始使用" })).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
