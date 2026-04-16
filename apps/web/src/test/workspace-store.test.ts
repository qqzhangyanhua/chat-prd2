import { describe, expect, it } from "vitest";
import prdMetaCases from "../../../../docs/contracts/prd-meta-cases.json";

import type { AgentTurnDecision, SessionSnapshotResponse, StateSnapshotResponse } from "../lib/types";
import { parseEventStream } from "../lib/sse";
import { createWorkspaceStore } from "../store/workspace-store";

function buildSnapshotWithDecisions(
  decisions?: AgentTurnDecision[],
  state?: StateSnapshotResponse,
): SessionSnapshotResponse {
  return {
    session: {
      id: "session-1",
      user_id: "user-1",
      title: "AI Co-founder",
      initial_idea: "idea",
      created_at: "2026-04-05T00:00:00Z",
      updated_at: "2026-04-05T00:00:00Z",
    },
    state: state ?? {},
    prd_snapshot: {
      sections: {},
    },
    prd_review: {
      verdict: "needs_input",
      status: "drafting",
      summary: "仍需继续补齐关键章节。",
      checks: {},
      gaps: [],
      missing_sections: [],
      ready_for_confirmation: false,
    },
    replay_timeline: [],
    messages: [],
    assistant_reply_groups: [],
    turn_decisions: decisions,
  };
}

describe("workspace store", () => {
  it("hydrates first draft from structured snapshot without mutating prd panel state", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession(
      buildSnapshotWithDecisions([], {
        prd_draft: {
          version: 2,
          status: "drafting",
          sections: {
            target_user: {
              title: "目标用户",
              completeness: "partial",
              entries: [
                {
                  id: "entry-target-user-1",
                  text: "第一版先服务独立开发者。",
                  assertion_state: "confirmed",
                  evidence_ref_ids: ["evidence-user-1"],
                },
              ],
            },
          },
          summary: {
            section_keys: ["target_user"],
            entry_ids: ["entry-target-user-1"],
            evidence_ids: ["evidence-user-1"],
          },
        },
        evidence: [
          {
            id: "evidence-user-1",
            kind: "user_message",
            excerpt: "我想先服务独立开发者。",
            section_keys: ["target_user"],
          },
        ],
      }),
    );

    expect(store.getState().firstDraft.sections.target_user?.entries[0]?.assertionState).toBe("confirmed");
    expect(store.getState().firstDraft.evidenceRegistry["evidence-user-1"]?.kind).toBe("user_message");
    expect(store.getState().prd.sections.target_user?.content).not.toBe("第一版先服务独立开发者。");
  });

  it("merges draft.updated into firstDraft and does not mutate prd panel state", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "draft.updated",
      data: {
        sections: {
          target_user: {
            title: "目标用户",
            completeness: "partial",
            entries: [
              {
                id: "entry-target-user-1",
                text: "第一版先服务独立开发者。",
                assertion_state: "confirmed",
                evidence_ref_ids: ["evidence-user-1"],
              },
            ],
          },
        },
        evidence_registry: [
          {
            id: "evidence-user-1",
            kind: "user_message",
            excerpt: "我想先服务独立开发者。",
            section_keys: ["target_user"],
          },
        ],
        draft_summary: {
          version: 2,
          section_keys: ["target_user"],
          entry_ids: ["entry-target-user-1"],
          evidence_ids: ["evidence-user-1"],
        },
        sections_changed: ["target_user"],
        entry_ids: ["entry-target-user-1"],
      },
    });

    expect(store.getState().firstDraft.latestUpdates.entryIds).toEqual(["entry-target-user-1"]);
    expect(store.getState().firstDraft.sections.target_user?.entries[0]?.evidenceRefIds).toEqual(["evidence-user-1"]);
    expect(store.getState().prd.sections.target_user?.content).not.toBe("第一版先服务独立开发者。");
  });

  it("ignores stale snapshot first draft versions", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "draft.updated",
      data: {
        sections: {
          target_user: {
            title: "目标用户",
            completeness: "partial",
            entries: [
              {
                id: "entry-target-user-2",
                text: "先服务设计师。",
                assertion_state: "inferred",
                evidence_ref_ids: ["evidence-user-2"],
              },
            ],
          },
        },
        evidence_registry: [
          {
            id: "evidence-user-2",
            kind: "system_inference",
            excerpt: "当前先按设计师方向推断。",
            section_keys: ["target_user"],
          },
        ],
        draft_summary: {
          version: 3,
          section_keys: ["target_user"],
          entry_ids: ["entry-target-user-2"],
          evidence_ids: ["evidence-user-2"],
        },
        sections_changed: ["target_user"],
        entry_ids: ["entry-target-user-2"],
      },
    });

    store.getState().refreshSessionSnapshot(
      buildSnapshotWithDecisions([], {
        prd_draft: {
          version: 2,
          status: "drafting",
          sections: {
            target_user: {
              title: "目标用户",
              completeness: "partial",
              entries: [
                {
                  id: "entry-target-user-1",
                  text: "第一版先服务独立开发者。",
                  assertion_state: "confirmed",
                  evidence_ref_ids: ["evidence-user-1"],
                },
              ],
            },
          },
        },
        evidence: [
          {
            id: "evidence-user-1",
            kind: "user_message",
            excerpt: "我想先服务独立开发者。",
            section_keys: ["target_user"],
          },
        ],
      }),
    );

    expect(store.getState().firstDraft.sections.target_user?.entries[0]?.text).toBe("先服务设计师。");
  });

  it("updates prd panel when prd.updated event arrives", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {
          target_user: {
            content: "独立开发者仍然是当前最优先的一类目标用户。",
            status: "inferred",
            title: "目标用户",
          },
        },
      },
    });

    expect(store.getState().prd.sections.target_user?.content).toBe(
      "独立开发者仍然是当前最优先的一类目标用户。",
    );
  });

  it("hydrates prd panel snapshot gap and changed state from phase4 contract", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
      },
      prd_snapshot: {
        sections: {
          target_user: {
            title: "目标用户",
            content: "独立开发者",
            status: "confirmed",
          },
          problem: {
            title: "核心问题",
            content: "需求确认成本高",
            status: "inferred",
          },
          risks_to_validate: {
            title: "待验证 / 风险",
            content: "需确认：付费意愿尚未验证",
            status: "inferred",
          },
          open_questions: {
            title: "待确认问题",
            content: "是否需要团队协作仍待确认",
            status: "inferred",
          },
        },
        meta: {
          stageLabel: "草稿中",
          stageTone: "draft",
          criticSummary: "当前还有关键缺口待补齐。",
          criticGaps: [],
          draftVersion: 3,
          nextQuestion: null,
        },
        sections_changed: ["target_user", "open_questions"],
        missing_sections: ["solution", "mvp_scope"],
        gap_prompts: ["请补充「solution」内容", "请补充「mvp_scope」内容"],
        ready_for_confirmation: false,
      } as SessionSnapshotResponse["prd_snapshot"],
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.sectionsChanged).toEqual(["target_user", "open_questions"]);
    expect(store.getState().prd.missingSections).toEqual(["solution", "mvp_scope"]);
    expect(store.getState().prd.gapPrompts).toEqual(["请补充「solution」内容", "请补充「mvp_scope」内容"]);
    expect(store.getState().prd.readyForConfirmation).toBe(false);
    expect(store.getState().prd.meta.stageLabel).toBe("草稿中");
  });

  it("merges prd panel changed sections and ready state from prd.updated event", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {
          solution: {
            title: "解决方案",
            content: "先做浏览器内预览和分享闭环。",
            status: "confirmed",
          },
          success_metrics: {
            title: "成功指标",
            content: "7 天内完成一版可确认初稿。",
            status: "confirmed",
          },
        },
        meta: {
          stageLabel: "可确认初稿",
          stageTone: "ready",
          criticSummary: "关键信息已基本齐备，可以给用户确认当前 PRD 初稿。",
          criticGaps: [],
          draftVersion: 4,
          nextQuestion: null,
        },
        sections_changed: ["solution", "success_metrics"],
        missing_sections: [],
        gap_prompts: [],
        ready_for_confirmation: true,
      } as Record<string, unknown>,
    });

    expect(store.getState().prd.sections.solution?.content).toBe("先做浏览器内预览和分享闭环。");
    expect(store.getState().prd.sectionsChanged).toEqual(["solution", "success_metrics"]);
    expect(store.getState().prd.readyForConfirmation).toBe(true);
    expect(store.getState().prd.meta.stageLabel).toBe("可确认初稿");
  });

  it("routes phase4 panel sections into the ordered prd state when prd.updated event arrives", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {
          solution: {
            content: "先做浏览器内预览、评论和分享闭环。",
            status: "inferred",
            title: "解决方案",
          },
          constraints: {
            content: "首版只支持浏览器端，不做桌面插件。",
            status: "confirmed",
            title: "约束条件",
          },
          success_metrics: {
            content: "7 天内至少完成 10 次有效预览。",
            status: "inferred",
            title: "成功指标",
          },
        },
      },
    });

    expect(store.getState().prd.sections.solution?.content).toBe(
      "先做浏览器内预览、评论和分享闭环。",
    );
    expect(store.getState().prd.sections.constraints?.content).toBe(
      "首版只支持浏览器端，不做桌面插件。",
    );
    expect(store.getState().prd.sections.success_metrics?.content).toBe(
      "7 天内至少完成 10 次有效预览。",
    );
  });

  it("updates prd meta when prd.updated event includes meta", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {},
        meta: {
          stageLabel: "可整理终稿",
          stageTone: "ready",
          criticSummary: "Critic 已通过，可以整理最终版 PRD。",
          criticGaps: ["缺少风险边界"],
          draftVersion: 3,
          nextQuestion: "如果你确认无误，我可以开始整理最终版 PRD。",
        },
      },
    });

    expect(store.getState().prd.meta.stageLabel).toBe("可整理终稿");
    expect(store.getState().prd.meta.stageTone).toBe("ready");
    expect(store.getState().prd.meta.draftVersion).toBe(3);
    expect(store.getState().prd.meta.criticGaps).toEqual(["缺少风险边界"]);
    expect(store.getState().prd.meta.nextQuestion).toBe("如果你确认无误，我可以开始整理最终版 PRD。");
  });

  it("appends assistant delta into the active assistant message", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-1",
        session_id: "session-1",
      },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先继续明确他们最痛的一次产品决策卡点。",
        is_regeneration: false,
        is_latest: false,
      },
    });

    expect(store.getState().messages.at(-1)?.content).toBe(
      "先继续明确他们最痛的一次产品决策卡点。",
    );
    expect(store.getState().messages.at(-1)?.role).toBe("assistant");
  });

  it("records the latest accepted user input for regeneration", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-1",
        session_id: "session-1",
      },
    });

    expect(store.getState().lastSubmittedInput).toBe("我想先服务独立开发者");
  });

  it("updates decision guidance immediately when decision.ready arrives", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "decision.ready",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        phase: "solution",
        conversation_strategy: "converge",
        next_move: "assume_and_advance",
        suggestions: [
          {
            label: "先讲方案主线",
            content: "我想先说明这个产品第一版最核心的解决方式是什么。",
            rationale: "先讲主线方案，能避免功能堆砌。",
            priority: 1,
            type: "direction",
          },
          {
            label: "先讲差异化",
            content: "我想先比较这个产品和现有做法最大的不同是什么。",
            rationale: "差异化清楚了，方案价值才站得住。",
            priority: 2,
            type: "tradeoff",
          },
        ],
        recommendation: {
          label: "先讲方案主线",
          content: "我想先说明这个产品第一版最核心的解决方式是什么。",
        },
        response_mode: "options_first",
        guidance_mode: "narrow",
        guidance_step: "choose",
        focus_dimension: "solution",
        transition_reason: "当前方案方向还不够稳定，先从两个候选主线里选一个。",
        transition_trigger: "high_uncertainty",
        option_cards: [
          {
            id: "solution-1-mainline",
            label: "先讲方案主线",
            title: "先讲方案主线",
            content: "我想先说明这个产品第一版最核心的解决方式是什么。",
            description: "先讲主线方案，能避免功能堆砌。",
            type: "direction",
            priority: 1,
          },
        ],
        freeform_affordance: {
          label: "都不对，我补充",
          value: "freeform",
          kind: "freeform",
        },
        available_mode_switches: [
          {
            mode: "confirm",
            label: "直接进入确认",
          },
        ],
        next_best_questions: [
          "我想先说明这个产品第一版最核心的解决方式是什么。",
          "我想先比较这个产品和现有做法最大的不同是什么。",
        ],
      },
    });

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "converge",
      strategyLabel: "收敛中",
      strategyReason: "当前方案方向还不够稳定，先从两个候选主线里选一个。",
      guidanceMode: "narrow",
      guidanceStep: "choose",
      focusDimension: "solution",
      transitionReason: "当前方案方向还不够稳定，先从两个候选主线里选一个。",
      responseMode: "options_first",
      nextBestQuestions: [
        "我想先说明这个产品第一版最核心的解决方式是什么。",
        "我想先比较这个产品和现有做法最大的不同是什么。",
      ],
      confirmQuickReplies: [],
      optionCards: [
        {
          id: "solution-1-mainline",
          label: "先讲方案主线",
          title: "先讲方案主线",
          content: "我想先说明这个产品第一版最核心的解决方式是什么。",
          description: "先讲主线方案，能避免功能堆砌。",
          type: "direction",
          priority: 1,
        },
      ],
      freeformAffordance: {
        label: "都不对，我补充",
        value: "freeform",
        kind: "freeform",
      },
      availableModeSwitches: [
        {
          mode: "confirm",
          label: "直接进入确认",
        },
      ],
      suggestionOptions: [
        {
          label: "先讲方案主线",
          content: "我想先说明这个产品第一版最核心的解决方式是什么。",
          rationale: "先讲主线方案，能避免功能堆砌。",
          priority: 1,
          type: "direction",
        },
        {
          label: "先讲差异化",
          content: "我想先比较这个产品和现有做法最大的不同是什么。",
          rationale: "差异化清楚了，方案价值才站得住。",
          priority: 2,
          type: "tradeoff",
        },
      ],
    });
  });

  it("merges diagnostics from decision.ready into the open ledger", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession(buildSnapshotWithDecisions([], {
      diagnostics: [
        {
          id: "gap-solution",
          type: "gap",
          bucket: "unknown",
          status: "open",
          title: "方案主线缺失",
          detail: "还没有说清楚第一版如何解决问题。",
          impact_scope: ["solution"],
          suggested_next_step: {
            action_kind: "ask_user",
            label: "先说方案主线",
            prompt: "如果只保留一个核心动作，第一版到底怎么解决这个问题？",
          },
          confidence: "medium",
        },
      ],
      diagnostic_summary: {
        open_count: 1,
        unknown_count: 1,
        risk_count: 0,
        to_validate_count: 0,
      },
    }));

    store.getState().applyEvent({
      type: "decision.ready",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        phase: "problem",
        conversation_strategy: "clarify",
        next_move: "probe_for_specificity",
        suggestions: [],
        recommendation: null,
        next_best_questions: [],
        diagnostics: [
          {
            id: "assumption-web",
            type: "assumption",
            bucket: "risk",
            status: "open",
            title: "默认先做 Web 端",
            detail: "当前推进默认第一版只做 Web 端。",
            impact_scope: ["solution", "mvp_scope"],
            suggested_next_step: {
              action_kind: "ask_user",
              label: "确认首发载体",
              prompt: "你是不是已经决定第一版只做 Web 端？",
            },
            confidence: "medium",
          },
        ],
        diagnostic_summary: {
          open_count: 1,
          unknown_count: 0,
          risk_count: 1,
          to_validate_count: 0,
        },
        ledger_summary: {
          open_count: 2,
          unknown_count: 1,
          risk_count: 1,
          to_validate_count: 0,
        },
      },
    });

    expect(store.getState().latestDiagnostics).toHaveLength(1);
    expect(store.getState().diagnosticLedger).toHaveLength(2);
    expect(store.getState().diagnosticLedgerSummary).toEqual({
      openCount: 2,
      unknownCount: 1,
      riskCount: 1,
      toValidateCount: 0,
    });
  });

  it("keeps the fresher diagnostic ledger when a stale snapshot hydrates", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {},
        meta: {
          draftVersion: 4,
        },
      },
    });
    store.setState((state) => ({
      ...state,
      diagnosticLedger: [
        {
          id: "assumption-web",
          type: "assumption",
          bucket: "risk",
          status: "open",
          title: "默认先做 Web 端",
          detail: "当前推进默认第一版只做 Web 端。",
          impactScope: ["solution"],
          suggestedNextStep: {
            action_kind: "ask_user",
            label: "确认首发载体",
            prompt: "你是不是已经决定第一版只做 Web 端？",
          },
          confidence: "medium",
        },
      ],
      diagnosticLedgerSummary: {
        openCount: 1,
        unknownCount: 0,
        riskCount: 1,
        toValidateCount: 0,
      },
    }));

    store.getState().refreshSessionSnapshot(buildSnapshotWithDecisions([], {
      prd_draft: { version: 2 },
      diagnostics: [],
      diagnostic_summary: {
        open_count: 0,
        unknown_count: 0,
        risk_count: 0,
        to_validate_count: 0,
      },
    }));

    expect(store.getState().diagnosticLedger).toHaveLength(1);
    expect(store.getState().diagnosticLedgerSummary).toEqual({
      openCount: 1,
      unknownCount: 0,
      riskCount: 1,
      toValidateCount: 0,
    });
  });

  it("hydrates decision guidance from session snapshot without re-deriving mode from old fields", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession(buildSnapshotWithDecisions([
      {
        id: "decision-1",
        session_id: "session-1",
        user_message_id: "user-1",
        phase: "problem",
        next_move: "force_rank_or_choose",
        created_at: "2026-04-05T00:00:00Z",
        state_patch_json: {
          conversation_strategy: "choose",
          guidance_mode: "compare",
          guidance_step: "compare",
          focus_dimension: "problem",
          transition_reason: "候选问题不止一个，先做取舍。",
          response_mode: "options_first",
          freeform_affordance: {
            label: "都不对，我补充",
            value: "freeform",
            kind: "freeform",
          },
          available_mode_switches: [{ mode: "confirm", label: "直接进入确认" }],
        },
        decision_sections: [
          {
            key: "judgement",
            meta: {
              conversation_strategy: "choose",
              strategy_label: "推动取舍",
              strategy_reason: "候选问题不止一个，先做取舍。",
              guidance_mode: "compare",
              guidance_step: "compare",
              focus_dimension: "problem",
              transition_reason: "候选问题不止一个，先做取舍。",
            },
          },
          {
            key: "next_step",
            meta: {
              next_best_questions: ["先讲最高频问题", "先讲最痛一刻"],
              suggestion_options: [],
              option_cards: [
                {
                  id: "problem-1",
                  label: "先讲最高频问题",
                  title: "先讲最高频问题",
                  content: "我想先讲清楚最高频的那个问题。",
                  description: "先锁定高频，再看值不值得做。",
                  type: "direction",
                  priority: 1,
                },
              ],
              freeform_affordance: {
                label: "都不对，我补充",
                value: "freeform",
                kind: "freeform",
              },
              available_mode_switches: [{ mode: "confirm", label: "直接进入确认" }],
              guidance_mode: "compare",
              guidance_step: "compare",
              focus_dimension: "problem",
              transition_reason: "候选问题不止一个，先做取舍。",
              response_mode: "options_first",
            },
          },
        ],
      },
    ], {
      guidance_mode: "compare",
      guidance_step: "compare",
      focus_dimension: "problem",
      transition_reason: "候选问题不止一个，先做取舍。",
      response_mode: "options_first",
      freeform_affordance: {
        label: "都不对，我补充",
        value: "freeform",
        kind: "freeform",
      },
      available_mode_switches: [{ mode: "confirm", label: "直接进入确认" }],
    }));

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "choose",
      strategyLabel: "推动取舍",
      strategyReason: "候选问题不止一个，先做取舍。",
      guidanceMode: "compare",
      guidanceStep: "compare",
      focusDimension: "problem",
      transitionReason: "候选问题不止一个，先做取舍。",
      responseMode: "options_first",
      nextBestQuestions: ["先讲最高频问题", "先讲最痛一刻"],
      confirmQuickReplies: [],
      optionCards: [
        {
          id: "problem-1",
          label: "先讲最高频问题",
          title: "先讲最高频问题",
          content: "我想先讲清楚最高频的那个问题。",
          description: "先锁定高频，再看值不值得做。",
          type: "direction",
          priority: 1,
        },
      ],
      freeformAffordance: {
        label: "都不对，我补充",
        value: "freeform",
        kind: "freeform",
      },
      availableModeSwitches: [{ mode: "confirm", label: "直接进入确认" }],
    });
  });

  it("closes streaming state and preserves accepted user message when assistant.error arrives", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-1",
        session_id: "session-1",
      },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先继续明确他们最痛的一次产品决策卡点。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.error",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        model_config_id: "model-openai",
        code: "MODEL_STREAM_FAILED",
        message: "流式中断",
        recovery_action: {
          type: "retry",
          label: "稍后重试",
          target: null,
        },
        is_regeneration: false,
        is_latest: false,
      },
    });

    expect(store.getState().errorMessage).toBe("流式中断");
    expect(store.getState().isStreaming).toBe(false);
    expect(store.getState().streamPhase).toBe("idle");
    expect(store.getState().messages.some((message) => message.role === "user" && message.id === "user-1")).toBe(true);
    expect(store.getState().activeAssistantVersionId).toBeNull();
    expect(store.getState().activeReplyGroupId).toBeNull();
  });

  it("marks the latest assistant draft as interrupted after manual cancel", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().markInterrupted();

    expect(store.getState().lastInterrupted).toBe(true);
  });

  it("starts regenerate without removing the last assistant message", () => {
    const store = createWorkspaceStore();
    store.getState().setAvailableModelConfigs([
      {
        id: "model-openai",
        name: "OpenAI GPT-4.1",
        model: "gpt-4.1",
      },
    ]);

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: {
        message_id: "user-1",
        session_id: "session-1",
      },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_id: "version-1",
        version_no: 1,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        is_regeneration: false,
        is_latest: true,
        message_id: "assistant-1",
      },
    });
    const regenerateInput = store.getState().startRegenerate();

    expect(regenerateInput).toBe(true);
    expect(store.getState().messages.filter((message) => message.role === "user")).toHaveLength(1);
    expect(store.getState().messages.at(-1)?.role).toBe("assistant");
  });

  it("clears the interrupted marker when a new request starts", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "先讲讲他们在定义 MVP 时最常卡住的地方。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().markInterrupted();

    store.getState().startRequest("继续往下问");

    expect(store.getState().lastInterrupted).toBe(false);
  });

  it("clears inputValue immediately when a request is started", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想服务独立开发者");

    expect(store.getState().inputValue).toBe("");
  });

  it("hydrates a recovered session and loads messages from snapshot", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("继续追问");
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "继续往下收敛。",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().markInterrupted();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        idea: "idea",
        stage_hint: "明确问题",
      },
      prd_snapshot: {
        sections: {
          target_user: {
            title: "目标用户",
            content: "独立开发者",
            status: "confirmed",
          },
        },
      },
      messages: [
        {
          id: "m1",
          session_id: "session-1",
          role: "user",
          content: "你好",
          message_type: "chat",
        },
        {
          id: "m2",
          session_id: "session-1",
          role: "assistant",
          content: "你好，请问你的想法是？",
          message_type: "chat",
        },
      ],
      assistant_reply_groups: [],
    });

    expect(store.getState().inputValue).toBe("");
    expect(store.getState().messages).toHaveLength(2);
    expect(store.getState().messages[0]).toMatchObject({ role: "user", content: "你好" });
    expect(store.getState().messages[1]).toMatchObject({
      role: "assistant",
      content: "你好，请问你的想法是？",
    });
    expect(store.getState().replyGroups).toEqual({});
    expect(store.getState().selectedHistoryGroupId).toBeNull();
    expect(store.getState().selectedHistoryVersionId).toBeNull();
    expect(store.getState().currentAction).toBeNull();
    expect(store.getState().isStreaming).toBe(false);
    expect(store.getState().pendingUserInput).toBeNull();
    expect(store.getState().lastInterrupted).toBe(false);
    expect(store.getState().lastSubmittedInput).toBeNull();
    expect(store.getState().prd.sections.target_user?.content).toBe("独立开发者");
  });

  it("hydrates runtime model scene and collaboration label from snapshot state", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        idea: "idea",
        stage_hint: "明确问题",
        current_model_scene: "reasoning",
        collaboration_mode_label: "深度推演模式",
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().currentModelScene).toBe("reasoning");
    expect(store.getState().collaborationModeLabel).toBe("深度推演模式");
  });

  it("hydrates explicit workflow status flags from snapshot state", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "finalize",
        finalization_ready: true,
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().workflowStage).toBe("finalize");
    expect(store.getState().isFinalizeReady).toBe(true);
    expect(store.getState().isCompleted).toBe(false);
  });

  it("hydrates legacy backfilled snapshot with explicit closure fields", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "finalize",
        finalization_ready: true,
        prd_draft: {
          version: 3,
          status: "draft_refined",
          sections: {},
        },
        critic_result: {
          overall_verdict: "pass",
          question_queue: [],
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().workflowStage).toBe("finalize");
    expect(store.getState().isFinalizeReady).toBe(true);
    expect(store.getState().prd.meta.stageLabel).toBe("可整理终稿");
  });

  it("derives prd meta as drafting when workflow is refine_loop", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
        prd_draft: {
          version: 2,
          status: "draft_refined",
        },
        critic_result: {
          overall_verdict: "revise",
          major_gaps: ["缺少成功指标", "缺少不做清单"],
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.meta.stageLabel).toBe("草稿中");
    expect(store.getState().prd.meta.draftVersion).toBe(2);
    expect(store.getState().prd.meta.criticSummary).toContain("2 个关键缺口");
    expect(store.getState().prd.meta.criticGaps).toEqual(["缺少成功指标", "缺少不做清单"]);
    expect(store.getState().prd.meta.nextQuestion).toBeNull();
  });

  it("derives prd meta as ready when finalization is available", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "finalize",
        finalization_ready: true,
        prd_draft: {
          version: 3,
          status: "draft_refined",
        },
        critic_result: {
          overall_verdict: "pass",
          question_queue: [],
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.meta.stageLabel).toBe("可整理终稿");
    expect(store.getState().prd.meta.criticSummary).toContain("Critic 已通过");
    expect(store.getState().prd.meta.criticGaps).toEqual([]);
    expect(store.getState().prd.meta.nextQuestion).toBeNull();
  });

  it("derives prd meta as finalized when workflow is completed", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "completed",
        prd_draft: {
          version: 4,
          status: "finalized",
        },
        finalization_ready: true,
        critic_result: {
          overall_verdict: "pass",
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.meta.stageLabel).toBe("已生成终稿");
    expect(store.getState().prd.meta.criticSummary).toContain("最终版");
    expect(store.getState().prd.meta.criticGaps).toEqual([]);
    expect(store.getState().prd.meta.nextQuestion).toBeNull();
  });

  it("updates explicit status flags when completed session is reopened to refine_loop", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "completed",
        finalization_ready: true,
        prd_draft: {
          version: 4,
          status: "finalized",
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    store.getState().refreshSessionSnapshot({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
        finalization_ready: false,
        prd_draft: {
          version: 5,
          status: "draft_refined",
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().workflowStage).toBe("refine_loop");
    expect(store.getState().isFinalizeReady).toBe(false);
    expect(store.getState().isCompleted).toBe(false);
  });

  it("keeps completed semantics when refreshed snapshot is older", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "completed",
        finalization_ready: true,
        prd_draft: {
          version: 6,
          status: "finalized",
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    store.getState().refreshSessionSnapshot({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
        finalization_ready: false,
        prd_draft: {
          version: 5,
          status: "draft_refined",
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().workflowStage).toBe("completed");
    expect(store.getState().isFinalizeReady).toBe(true);
    expect(store.getState().isCompleted).toBe(true);
  });

  it("derives prd meta next question from critic queue", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
        prd_draft: {
          version: 2,
          status: "draft_refined",
        },
        critic_result: {
          overall_verdict: "block",
          major_gaps: ["缺少权限边界"],
          question_queue: ["权限边界怎么定：哪些人可以查看/编辑/分享？"],
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.meta.nextQuestion).toBe("权限边界怎么定：哪些人可以查看/编辑/分享？");
  });

  it("matches the shared prd meta contract cases", () => {
    for (const contractCase of prdMetaCases) {
      const store = createWorkspaceStore();

      store.getState().hydrateSession({
        session: {
          id: "session-1",
          user_id: "user-1",
          title: "AI Co-founder",
          initial_idea: "idea",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
        },
        state: contractCase.state as StateSnapshotResponse,
        prd_snapshot: {
          sections: {},
        },
        messages: [],
        assistant_reply_groups: [],
      });

      expect(store.getState().prd.meta).toEqual(contractCase.expected);
    }
  });

  it("derives extra prd sections from prd_draft sections", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
        prd_draft: {
          version: 2,
          status: "draft_refined",
          sections: {
            constraints: {
              title: "约束条件",
              content: "首版优先浏览器端，不做桌面插件。",
              status: "confirmed",
            },
            success_metrics: {
              title: "成功指标",
              content: "7 日内至少有 5 个团队完成一次完整预览。",
              status: "inferred",
            },
          },
        },
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.sections.constraints?.content).toContain("浏览器端");
    expect(store.getState().prd.sections.success_metrics?.content).toContain("5 个团队");
  });

  it("prefers prd_draft primary sections over legacy prd snapshot", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
        prd_draft: {
          version: 2,
          status: "draft_refined",
          sections: {
            target_user: {
              title: "目标用户",
              content: "草稿用户",
              status: "confirmed",
            },
            solution: {
              title: "解决方案",
              content: "草稿方案",
              status: "inferred",
            },
          },
        },
      },
      prd_snapshot: {
        sections: {
          target_user: {
            title: "目标用户",
            content: "旧快照用户",
            status: "confirmed",
          },
          problem: {
            title: "核心问题",
            content: "旧快照问题",
            status: "confirmed",
          },
          solution: {
            title: "解决方案",
            content: "旧快照方案",
            status: "confirmed",
          },
          mvp_scope: {
            title: "MVP 范围",
            content: "旧快照范围",
            status: "confirmed",
          },
        },
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.sections.target_user?.content).toBe("草稿用户");
    expect(store.getState().prd.sections.solution?.content).toBe("草稿方案");
    expect(store.getState().prd.sections.problem?.content).toBe("旧快照问题");
    expect(store.getState().prd.sections.mvp_scope?.content).toBe("旧快照范围");
  });

  it("hydrates legacy snapshot when assistant_reply_groups is missing", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        idea: "idea",
        stage_hint: "明确问题",
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [
        {
          id: "user-1",
          session_id: "session-1",
          role: "user",
          content: "你好",
          message_type: "chat",
        },
      ],
    });

    expect(store.getState().messages).toHaveLength(1);
    expect(store.getState().replyGroups).toEqual({});
  });

  it("refreshes session snapshot without clearing current action or typed input", () => {
    const store = createWorkspaceStore();

    store.setState({
      ...store.getState(),
      currentAction: {
        action: "probe_deeper",
        target: "problem",
        reason: "继续澄清问题边界",
      },
      inputValue: "我已经开始输入下一条了",
      lastSubmittedInput: "上一轮输入",
      isStreaming: false,
    });

    store.getState().refreshSessionSnapshot({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        idea: "idea",
        stage_hint: "明确问题",
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [
        {
          id: "user-1",
          session_id: "session-1",
          role: "user",
          content: "上一轮用户输入",
          message_type: "chat",
        },
        {
          id: "assistant-1",
          session_id: "session-1",
          role: "assistant",
          content: "刷新后的回复",
          message_type: "chat",
        },
      ],
      assistant_reply_groups: [],
      turn_decisions: [
        {
          id: "decision-1",
          session_id: "session-1",
          created_at: "2026-04-07T10:00:00Z",
          state_patch_json: {
            conversation_strategy: "confirm",
            strategy_reason: "需要确认最新范围",
            next_best_questions: ["确认下一步优先级"],
          },
        },
      ],
    });

    expect(store.getState().currentAction).toEqual({
      action: "probe_deeper",
      target: "problem",
      reason: "继续澄清问题边界",
    });
    expect(store.getState().inputValue).toBe("我已经开始输入下一条了");
    expect(store.getState().lastSubmittedInput).toBe("上一轮输入");
    expect(store.getState().messages.at(-1)?.content).toBe("刷新后的回复");
    expect(store.getState().decisionGuidance?.strategyLabel).toBe("确认中");
  });

  it("does not let a stale refreshed snapshot overwrite a newer streamed prd state", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {
          solution: {
            title: "解决方案",
            content: "更新后的方案 v3",
            status: "confirmed",
          },
          constraints: {
            title: "约束条件",
            content: "更新后的约束 v3",
            status: "confirmed",
          },
        },
        meta: {
          stageLabel: "可整理终稿",
          stageTone: "ready",
          criticSummary: "Critic 已通过，可以整理最终版 PRD。",
          criticGaps: [],
          draftVersion: 3,
          nextQuestion: "是否开始整理终稿？",
        },
      },
    });

    store.getState().refreshSessionSnapshot({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
        prd_draft: {
          version: 2,
          status: "draft_refined",
          sections: {
            solution: {
              title: "解决方案",
              content: "旧快照方案 v2",
              status: "inferred",
            },
            constraints: {
              title: "约束条件",
              content: "旧快照约束 v2",
              status: "inferred",
            },
          },
        },
        critic_result: {
          overall_verdict: "revise",
          major_gaps: ["还缺一个关键问题"],
          question_queue: ["请继续补充范围边界"],
        },
      },
      prd_snapshot: {
        sections: {
          solution: {
            title: "解决方案",
            content: "旧快照方案 v2",
            status: "inferred",
          },
        },
      },
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.meta.draftVersion).toBe(3);
    expect(store.getState().prd.meta.stageLabel).toBe("可整理终稿");
    expect(store.getState().prd.sections.solution?.content).toBe("更新后的方案 v3");
    expect(store.getState().prd.sections.constraints?.content).toBe("更新后的约束 v3");
  });

  it("keeps fresher prd panel changed state when refreshed snapshot is stale", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {
          solution: {
            title: "解决方案",
            content: "更新后的方案 v4",
            status: "confirmed",
          },
        },
        meta: {
          stageLabel: "可确认初稿",
          stageTone: "ready",
          criticSummary: "可以确认初稿。",
          criticGaps: [],
          draftVersion: 4,
          nextQuestion: null,
        },
        sections_changed: ["solution"],
        missing_sections: [],
        gap_prompts: [],
        ready_for_confirmation: true,
      } as Record<string, unknown>,
    });

    store.getState().refreshSessionSnapshot({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        workflow_stage: "refine_loop",
        prd_draft: {
          version: 3,
          status: "draft_refined",
        },
      },
      prd_snapshot: {
        sections: {
          solution: {
            title: "解决方案",
            content: "旧快照方案 v3",
            status: "inferred",
          },
        },
        meta: {
          stageLabel: "草稿中",
          stageTone: "draft",
          criticSummary: "旧快照仍需补充。",
          criticGaps: ["缺少范围边界"],
          draftVersion: 3,
          nextQuestion: "请继续补充范围边界",
        },
        sections_changed: ["problem"],
        missing_sections: ["mvp_scope"],
        gap_prompts: ["请补充「mvp_scope」内容"],
        ready_for_confirmation: false,
      } as SessionSnapshotResponse["prd_snapshot"],
      messages: [],
      assistant_reply_groups: [],
    });

    expect(store.getState().prd.meta.draftVersion).toBe(4);
    expect(store.getState().prd.sections.solution?.content).toBe("更新后的方案 v4");
    expect(store.getState().prd.sectionsChanged).toEqual(["solution"]);
    expect(store.getState().prd.readyForConfirmation).toBe(true);
  });

  it("resets prd sections when the loaded session has an empty snapshot", () => {
    const store = createWorkspaceStore();

    store.getState().applyEvent({
      type: "prd.updated",
      data: {
        sections: {
          target_user: {
            title: "目标用户",
            content: "上一会话的目标用户",
            status: "confirmed",
          },
        },
      },
    });

    store.getState().hydrateSession({
      session: {
        id: "session-2",
        user_id: "user-1",
        title: "新的空白会话",
        initial_idea: "new idea",
        created_at: "2026-04-06T00:00:00Z",
        updated_at: "2026-04-06T00:00:00Z",
      },
      state: {
        idea: "new idea",
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [],
    });

    expect(store.getState().prd.sections.target_user?.content).not.toBe("上一会话的目标用户");
    expect(store.getState().prd.sections.target_user?.content).toBe(
      "还需要继续明确谁会最频繁、最迫切地使用这个产品。",
    );
  });

  it("stores reply groups and keeps old versions when regenerate completes", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: { message_id: "user-1", session_id: "session-1" },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "第一版",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_id: "version-1",
        version_no: 1,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        is_regeneration: false,
        is_latest: true,
        message_id: "assistant-1",
      },
    });

    store.getState().startRegenerate();
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        delta: "第二版",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 3,
        is_regeneration: true,
        is_latest: true,
      },
    });

    const group = store.getState().replyGroups["group-1"];
    expect(group).toBeDefined();
    expect(group.latestVersionId).toBe("version-2");
    expect(group.versions.map((version) => version.id)).toEqual(["version-1", "version-2"]);
    expect(group.versions[0].isLatest).toBe(false);
    expect(group.versions[1].isLatest).toBe(true);
    expect(store.getState().selectedHistoryGroupId).toBe("group-1");
    expect(store.getState().selectedHistoryVersionId).toBe("version-2");
    expect(store.getState().messages.at(-1)?.content).toBe("第二版");
  });

  it("stores assistant version createdAt when assistant.done arrives", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: { message_id: "user-1", session_id: "session-1" },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_no: 1,
        assistant_message_id: null,
        model_config_id: "model-openai",
        delta: "第一版",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_id: "version-1",
        version_no: 1,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        created_at: "2026-04-07T10:00:00Z",
        is_regeneration: false,
        is_latest: true,
        message_id: "assistant-1",
      },
    });

    expect(store.getState().replyGroups["group-1"]?.versions[0]).toMatchObject({
      id: "version-1",
      createdAt: "2026-04-07T10:00:00Z",
      isLatest: true,
    });
  });

  it("updates the visible assistant card after regenerate on a hydrated session", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      session: {
        id: "session-1",
        user_id: "user-1",
        title: "AI Co-founder",
        initial_idea: "idea",
        created_at: "2026-04-05T00:00:00Z",
        updated_at: "2026-04-05T00:00:00Z",
      },
      state: {
        idea: "idea",
        stage_hint: "明确问题",
      },
      prd_snapshot: {
        sections: {},
      },
      messages: [
        {
          id: "user-1",
          session_id: "session-1",
          role: "user",
          content: "你好",
          message_type: "chat",
        },
        {
          id: "version-1",
          session_id: "session-1",
          role: "assistant",
          content: "第一版",
          message_type: "chat",
          reply_group_id: "group-1",
          version_no: 1,
          is_latest: true,
        },
      ],
      assistant_reply_groups: [
        {
          id: "group-1",
          session_id: "session-1",
          user_message_id: "user-1",
          latest_version_id: "version-1",
          created_at: "2026-04-05T00:00:00Z",
          updated_at: "2026-04-05T00:00:00Z",
          versions: [
            {
              id: "version-1",
              reply_group_id: "group-1",
              session_id: "session-1",
              user_message_id: "user-1",
              version_no: 1,
              content: "第一版",
              action_snapshot: {},
              model_meta: {},
              state_version_id: "state-1",
              prd_snapshot_version: 1,
              created_at: "2026-04-05T00:00:00Z",
              is_latest: true,
            },
          ],
        },
      ],
    });

    store.getState().startRegenerate();
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-mirror-1",
        model_config_id: "model-openai",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.delta",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-mirror-1",
        model_config_id: "model-openai",
        delta: "第二版",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-mirror-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        is_regeneration: true,
        is_latest: true,
      },
    });

    expect(store.getState().messages.at(-1)).toMatchObject({
      id: "version-2",
      content: "第二版",
      replyGroupId: "group-1",
      versionNo: 2,
      isLatest: true,
    });
  });

  it("ignores stale assistant.done events for an older active version", () => {
    const store = createWorkspaceStore();

    store.getState().startRequest("我想先服务独立开发者");
    store.getState().applyEvent({
      type: "message.accepted",
      data: { message_id: "user-1", session_id: "session-1" },
    });
    store.getState().applyEvent({
      type: "reply_group.created",
      data: {
        reply_group_id: "group-1",
        user_message_id: "user-1",
        session_id: "session-1",
        is_regeneration: false,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.version.started",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-2",
        version_no: 2,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        is_regeneration: true,
        is_latest: false,
      },
    });
    store.getState().applyEvent({
      type: "assistant.done",
      data: {
        session_id: "session-1",
        user_message_id: "user-1",
        reply_group_id: "group-1",
        assistant_version_id: "version-1",
        version_id: "version-1",
        version_no: 1,
        assistant_message_id: "assistant-1",
        model_config_id: "model-openai",
        prd_snapshot_version: 2,
        is_regeneration: true,
        is_latest: true,
      },
    });

    expect(store.getState().activeAssistantVersionId).toBe("version-2");
    expect(store.getState().replyGroups["group-1"]?.latestVersionId).not.toBe("version-1");
  });
});

describe("decision guidance", () => {
  it("hydrates guidance from judgement and next_step sections", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-1",
        session_id: "session-1",
        created_at: "2026-04-07T10:00:00Z",
        decision_sections: [
          {
            key: "judgement",
            meta: {
              conversation_strategy: "converge",
              strategy_label: "收敛中",
              strategy_reason: "先收敛核心假设",
            },
          },
          {
            key: "next_step",
            meta: {
              next_best_questions: ["如果只能选一个主线怎么办？", "请告诉我下一步动作"],
            },
          },
        ],
        state_patch_json: {
          conversation_strategy: "choose",
          strategy_reason: "不应该使用",
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "converge",
      strategyLabel: "收敛中",
      strategyReason: "先收敛核心假设",
      nextBestQuestions: [
        "如果只能选一个主线怎么办？",
        "请告诉我下一步动作",
      ],
      confirmQuickReplies: [],
    });
  });

  it("falls back to state_patch_json when sections are incomplete and prefers judgement reason", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-2",
        session_id: "session-1",
        created_at: "2026-04-07T11:00:00Z",
        decision_sections: [
          {
            key: "judgement",
            meta: {
              strategy_reason: "判断来自 meta",
            },
          },
        ],
        state_patch_json: {
          conversation_strategy: "choose",
          next_best_questions: [
            " 先明确主线 ",
            "再问对方的关键指标",
            "再问对方的关键指标",
            "",
            "再确认细节",
          ],
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "choose",
      strategyLabel: "取舍中",
      strategyReason: "判断来自 meta",
      nextBestQuestions: [
        "先明确主线",
        "再问对方的关键指标",
        "再确认细节",
      ],
      confirmQuickReplies: [],
    });
  });

  it("hydrates confirm quick replies from next_step meta", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-confirm",
        session_id: "session-1",
        created_at: "2026-04-07T12:00:00Z",
        decision_sections: [
          {
            key: "judgement",
            meta: {
              conversation_strategy: "confirm",
              strategy_label: "确认中",
            },
          },
          {
            key: "next_step",
            meta: {
              next_best_questions: ["请确认当前理解是否准确"],
              confirm_quick_replies: [
                "确认，继续下一步",
                "不对，先改目标用户",
                "不对，先改核心问题",
              ],
            },
          },
        ],
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "confirm",
      strategyLabel: "确认中",
      strategyReason: null,
      nextBestQuestions: ["请确认当前理解是否准确"],
      confirmQuickReplies: [
        "确认，继续下一步",
        "不对，先改目标用户",
        "不对，先改核心问题",
      ],
    });
  });

  it("selects the latest decision by created_at and falls back to the last entry when timestamps are invalid", () => {
    const newestStore = createWorkspaceStore();
    const newestSnapshot = buildSnapshotWithDecisions([
      {
        id: "decision-old",
        session_id: "session-1",
        created_at: "2026-04-07T09:00:00Z",
        state_patch_json: {
          conversation_strategy: "clarify",
          strategy_reason: "老决策",
          next_best_questions: ["老推荐"],
        },
      },
      {
        id: "decision-new",
        session_id: "session-1",
        created_at: "2026-04-07T12:00:00Z",
        decision_sections: [
          {
            key: "judgement",
            meta: {
              conversation_strategy: "confirm",
              strategy_label: "确认中",
              strategy_reason: "最新决策",
            },
          },
          {
            key: "next_step",
            meta: {
              next_best_questions: ["请确认这个需求清单"],
            },
          },
        ],
      },
    ]);

    newestStore.getState().hydrateSession(newestSnapshot);
    expect(newestStore.getState().decisionGuidance?.strategyReason).toBe("最新决策");
    expect(newestStore.getState().decisionGuidance?.conversationStrategy).toBe("confirm");

    const mixStore = createWorkspaceStore();
    const mixSnapshot = buildSnapshotWithDecisions([
      {
        id: "decision-mix-old",
        session_id: "session-1",
        created_at: null,
        state_patch_json: {
          conversation_strategy: "clarify",
          strategy_reason: "不带时间戳",
        },
      },
      {
        id: "decision-mix-new",
        session_id: "session-1",
        created_at: "2026-04-07T20:00:00Z",
        state_patch_json: {
          conversation_strategy: "converge",
          strategy_reason: "最新时间",
          next_best_questions: ["继续推进"],
        },
      },
    ]);

    mixStore.getState().hydrateSession(mixSnapshot);
    expect(mixStore.getState().decisionGuidance?.strategyReason).toBe("最新时间");

    const fallbackStore = createWorkspaceStore();
    const fallbackSnapshot = buildSnapshotWithDecisions([
      {
        id: "decision-invalid",
        session_id: "session-1",
        created_at: "not-a-date",
        state_patch_json: {
          conversation_strategy: "choose",
          strategy_reason: "坏时间戳",
          next_best_questions: ["从最后一个决策"],
        },
      },
      {
        id: "decision-last",
        session_id: "session-1",
        state_patch_json: {
          conversation_strategy: "converge",
          strategy_reason: "数组尾部",
          next_best_questions: ["优先参考最后一条"],
        },
        decision_sections: [
          {
            key: "next_step",
            meta: {
              next_best_questions: ["优先参考最后一条"],
            },
          },
        ],
      },
    ]);

    fallbackStore.getState().hydrateSession(fallbackSnapshot);
    expect(fallbackStore.getState().decisionGuidance?.strategyReason).toBe("数组尾部");
  });

  it("chooses last entry when final decision lacks a valid created_at", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-old-valid",
        session_id: "session-1",
        created_at: "2026-04-07T08:00:00Z",
        state_patch_json: {
          conversation_strategy: "clarify",
          strategy_reason: "有效时间",
        },
      },
      {
        id: "decision-last-bad",
        session_id: "session-1",
        created_at: "not-a-date",
        state_patch_json: {
          conversation_strategy: "converge",
          strategy_reason: "最后一条",
          next_best_questions: ["看最后"],
        },
      },
    ]);

    store.getState().hydrateSession(snapshot);
    expect(store.getState().decisionGuidance?.strategyReason).toBe("最后一条");
  });

  it("hydrates structured suggestion options from next_step meta", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-suggestions",
        session_id: "session-1",
        created_at: "2026-04-07T10:00:00Z",
        decision_sections: [
          {
            key: "judgement",
            meta: {
              conversation_strategy: "greet",
              strategy_label: "欢迎引导",
              strategy_reason: "先给用户几个容易选择的方向。",
            },
          },
          {
            key: "next_step",
            meta: {
              suggestion_options: [
                {
                  label: "讨论产品想法",
                  content: "我有一个产品想法，想和你一起梳理成清晰的 PRD。",
                  rationale: "适合已经有方向、想快速进入产品讨论的情况。",
                  priority: 2,
                  type: "direction",
                },
                {
                  label: "从模糊方向开始",
                  content: "我现在只有一个模糊方向，还不知道怎么描述，想让你带着我一步步梳理。",
                  rationale: "适合还在很早期、需要 AI 先给框架的情况。",
                  priority: 1,
                  type: "direction",
                },
              ],
            },
          },
        ],
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "greet",
      strategyLabel: "欢迎引导",
      strategyReason: "先给用户几个容易选择的方向。",
      nextBestQuestions: [],
      confirmQuickReplies: [],
      suggestionOptions: [
        {
          label: "从模糊方向开始",
          content: "我现在只有一个模糊方向，还不知道怎么描述，想让你带着我一步步梳理。",
          rationale: "适合还在很早期、需要 AI 先给框架的情况。",
          priority: 1,
          type: "direction",
        },
        {
          label: "讨论产品想法",
          content: "我有一个产品想法，想和你一起梳理成清晰的 PRD。",
          rationale: "适合已经有方向、想快速进入产品讨论的情况。",
          priority: 2,
          type: "direction",
        },
      ],
    });
  });

  it("keeps guidance when only structured suggestion options are present", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-options-only",
        session_id: "session-1",
        created_at: "2026-04-07T14:00:00Z",
        decision_sections: [
          {
            key: "next_step",
            meta: {
              suggestion_options: [
                {
                  label: "先聊目标用户",
                  content: "我想先把目标用户讲清楚，再继续往下拆。",
                  rationale: "先定用户，后续问题和方案更容易收敛。",
                  priority: 1,
                  type: "direction",
                },
              ],
            },
          },
        ],
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance).toEqual({
      conversationStrategy: "clarify",
      strategyLabel: "澄清中",
      strategyReason: null,
      nextBestQuestions: [],
      confirmQuickReplies: [],
      suggestionOptions: [
        {
          label: "先聊目标用户",
          content: "我想先把目标用户讲清楚，再继续往下拆。",
          rationale: "先定用户，后续问题和方案更容易收敛。",
          priority: 1,
          type: "direction",
        },
      ],
    });
  });

  it("preserves all four structured suggestion options for mandatory abcd guidance", () => {
    const store = createWorkspaceStore();
    const snapshot = buildSnapshotWithDecisions([
      {
        id: "decision-options-abcd",
        session_id: "session-1",
        created_at: "2026-04-15T10:00:00Z",
        decision_sections: [
          {
            key: "next_step",
            meta: {
              suggestion_options: [
                {
                  label: "先聊验证方式",
                  content: "我想先聊第一轮要怎么验证这个想法值不值得做。",
                  rationale: "优先明确验证动作，降低空想风险。",
                  priority: 4,
                  type: "direction",
                },
                {
                  label: "先聊目标用户",
                  content: "我想先把目标用户讲清楚，再继续往下拆。",
                  rationale: "先定用户，后续问题和方案更容易收敛。",
                  priority: 1,
                  type: "direction",
                },
                {
                  label: "先聊核心痛点",
                  content: "我想先确认用户最痛的那个问题到底是什么。",
                  rationale: "先抓痛点，再看功能是否成立。",
                  priority: 3,
                  type: "direction",
                },
                {
                  label: "先聊使用场景",
                  content: "我想先把用户会在哪个场景下使用这款产品讲清楚。",
                  rationale: "先锁定场景，便于判断需求强度。",
                  priority: 2,
                  type: "direction",
                },
              ],
            },
          },
        ],
      },
    ]);

    store.getState().hydrateSession(snapshot);

    expect(store.getState().decisionGuidance?.suggestionOptions).toEqual([
      {
        label: "先聊目标用户",
        content: "我想先把目标用户讲清楚，再继续往下拆。",
        rationale: "先定用户，后续问题和方案更容易收敛。",
        priority: 1,
        type: "direction",
      },
      {
        label: "先聊使用场景",
        content: "我想先把用户会在哪个场景下使用这款产品讲清楚。",
        rationale: "先锁定场景，便于判断需求强度。",
        priority: 2,
        type: "direction",
      },
      {
        label: "先聊核心痛点",
        content: "我想先确认用户最痛的那个问题到底是什么。",
        rationale: "先抓痛点，再看功能是否成立。",
        priority: 3,
        type: "direction",
      },
      {
        label: "先聊验证方式",
        content: "我想先聊第一轮要怎么验证这个想法值不值得做。",
        rationale: "优先明确验证动作，降低空想风险。",
        priority: 4,
        type: "direction",
      },
    ]);
  });
});

describe("parseEventStream", () => {
  it("parses sse chunks into typed events", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: action.decided\ndata: {"action":"probe_deeper","target":"target_user","reason":"继续追问目标用户"}\n\n' +
              'event: assistant.delta\ndata: {"delta":"先把目标用户再缩窄一层。"}\n\n',
          ),
        );
        controller.close();
      },
    });

    const events = [];
    for await (const event of parseEventStream(stream)) {
      events.push(event);
    }

    expect(events).toEqual([
      {
        type: "action.decided",
        data: {
          action: "probe_deeper",
          target: "target_user",
          reason: "继续追问目标用户",
        },
      },
      {
        type: "assistant.delta",
        data: {
          delta: "先把目标用户再缩窄一层。",
        },
      },
    ]);
  });

  it("parses decision.ready events from sse chunks", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: decision.ready\ndata: {"session_id":"session-1","user_message_id":"user-1","phase":"problem","conversation_strategy":"clarify","next_move":"probe_for_specificity","suggestions":[{"label":"先讲高频麻烦","content":"我想先讲清楚，这个产品里最高频出现的那个麻烦是什么。","rationale":"先锁定高频问题，后面才容易判断值不值得做。","priority":1,"type":"direction"}],"recommendation":{"label":"先讲高频麻烦","content":"我想先讲清楚，这个产品里最高频出现的那个麻烦是什么。"},"next_best_questions":["我想先讲清楚，这个产品里最高频出现的那个麻烦是什么。"]}\n\n',
          ),
        );
        controller.close();
      },
    });

    const events = [];
    for await (const event of parseEventStream(stream)) {
      events.push(event);
    }

    expect(events).toEqual([
      {
        type: "decision.ready",
        data: {
          session_id: "session-1",
          user_message_id: "user-1",
          phase: "problem",
          conversation_strategy: "clarify",
          next_move: "probe_for_specificity",
          suggestions: [
            {
              label: "先讲高频麻烦",
              content: "我想先讲清楚，这个产品里最高频出现的那个麻烦是什么。",
              rationale: "先锁定高频问题，后面才容易判断值不值得做。",
              priority: 1,
              type: "direction",
            },
          ],
          recommendation: {
            label: "先讲高频麻烦",
            content: "我想先讲清楚，这个产品里最高频出现的那个麻烦是什么。",
          },
          next_best_questions: [
            "我想先讲清楚，这个产品里最高频出现的那个麻烦是什么。",
          ],
        },
      },
    ]);
  });

  it("stores prd review and replay timeline separately from prd panel sections", () => {
    const store = createWorkspaceStore();

    store.getState().hydrateSession({
      ...buildSnapshotWithDecisions([], {
        workflow_stage: "completed",
      }),
      prd_snapshot: {
        sections: {
          solution: {
            title: "解决方案",
            content: "单会话 replay",
            status: "confirmed",
          },
        },
      },
      prd_review: {
        verdict: "revise",
        status: "drafting",
        summary: "当前 PRD 结构已成型，但仍需补齐边界。",
        checks: {
          scope_boundary: {
            verdict: "needs_input",
            summary: "还缺明确边界。",
            evidence: [],
          },
        },
        gaps: ["请补充范围边界"],
        missing_sections: ["constraints"],
        ready_for_confirmation: false,
      },
      replay_timeline: [
        {
          id: "guidance-1",
          type: "guidance",
          title: "Guidance Decision",
          summary: "先把 guidance、diagnostics 和 PRD 变化串起来。",
          sections_changed: [],
          metadata: {},
        },
        {
          id: "export-1",
          type: "export",
          title: "Export Milestone",
          summary: "终稿已具备导出条件。",
          sections_changed: [],
          metadata: { file_name: "ai-cofounder-prd.md" },
        },
      ],
    });

    expect(store.getState().prd.sections.solution?.content).toBe("单会话 replay");
    expect(store.getState().prdReview?.summary).toBe("当前 PRD 结构已成型，但仍需补齐边界。");
    expect(store.getState().replayTimeline.map((item) => item.type)).toEqual(["guidance", "export"]);
    expect(store.getState().prd.sections.scope_boundary).toBeUndefined();
  });
});
