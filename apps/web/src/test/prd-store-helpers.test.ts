import { describe, expect, it } from "vitest";

import { deriveExtraPrdSections } from "../store/prd-store-helpers";

describe("deriveExtraPrdSections", () => {
  it("keeps only extra PRD sections with non-empty content", () => {
    const extraSections = deriveExtraPrdSections({
      prd_draft: {
        sections: {
          constraints: {
            title: "约束条件",
            content: "首版只支持浏览器端。",
            status: "confirmed",
          },
          success_metrics: {
            title: "成功指标",
            content: "   ",
            status: "inferred",
          },
          open_questions: {
            title: "待确认问题",
            content: "是否需要审批流？",
            status: "inferred",
          },
        },
      },
    });

    expect(extraSections).toEqual({
      constraints: {
        title: "约束条件",
        content: "首版只支持浏览器端。",
        status: "confirmed",
      },
      open_questions: {
        title: "待确认问题",
        content: "是否需要审批流？",
        status: "inferred",
      },
    });
    expect(extraSections.success_metrics).toBeUndefined();
  });
});
