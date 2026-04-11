import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "../app/page";

describe("HomePage", () => {
  it("renders the landing page hero without redirecting away from root", () => {
    render(<HomePage />);
    const loginLinks = screen.getAllByRole("link", { name: "登录" });

    expect(screen.getByText("AI 联合创始人")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "立即开始使用" })).toBeInTheDocument();
    expect(loginLinks.length).toBeGreaterThan(0);
    for (const link of loginLinks) {
      expect(link).toHaveAttribute("href", "/login");
    }
  });
});
