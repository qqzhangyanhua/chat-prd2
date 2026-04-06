import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssistantVersionHistoryDialog } from "../components/workspace/assistant-version-history-dialog";

describe("AssistantVersionHistoryDialog", () => {
  it("shows all assistant versions in the history dialog and highlights the latest one", () => {
    render(
      <AssistantVersionHistoryDialog
        onClose={() => {}}
        onSelectVersion={() => {}}
        open
        selectedVersionId="version-3"
        versions={[
          {
            assistantVersionId: "version-1",
            content: "第一版回复",
            isLatest: false,
            versionNo: 1,
          },
          {
            assistantVersionId: "version-2",
            content: "第二版回复",
            isLatest: false,
            versionNo: 2,
          },
          {
            assistantVersionId: "version-3",
            content: "第三版回复",
            isLatest: true,
            versionNo: 3,
          },
        ]}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: "重新生成历史" });

    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "查看版本 3" })).toBeInTheDocument();
    expect(within(dialog).getAllByText("当前版本")).toHaveLength(2);
    expect(within(dialog).getByText("第三版回复")).toBeInTheDocument();
  });

  it("switches version content without mutating the outer latest baseline", () => {
    const onSelectVersion = vi.fn();

    render(
      <AssistantVersionHistoryDialog
        onClose={() => {}}
        onSelectVersion={onSelectVersion}
        open
        selectedVersionId="version-3"
        versions={[
          {
            assistantVersionId: "version-2",
            content: "第二版回复",
            isLatest: false,
            versionNo: 2,
          },
          {
            assistantVersionId: "version-3",
            content: "第三版回复",
            isLatest: true,
            versionNo: 3,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "查看版本 2" }));

    expect(onSelectVersion).toHaveBeenCalledWith("version-2");
    expect(screen.getByText("第三版回复")).toBeInTheDocument();
  });
});
