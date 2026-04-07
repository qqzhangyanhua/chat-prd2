from __future__ import annotations

from typing import Any

from app.agent.types import Suggestion, TurnDecision


def build_suggestions(decision: TurnDecision) -> tuple[list[Suggestion], dict[str, Any] | None]:
    suggestions = _build_suggestions_for_move(decision)
    recommendation = _build_recommendation(suggestions)
    return suggestions, recommendation


def _build_recommendation(suggestions: list[Suggestion]) -> dict[str, Any] | None:
    if not suggestions:
        return None
    preferred_candidates = [item for item in suggestions if item.type == "recommendation"]
    if preferred_candidates:
        preferred = sorted(preferred_candidates, key=lambda item: (item.priority, item.label))[0]
    else:
        preferred = sorted(suggestions, key=lambda item: (item.priority, item.label))[0]
    return {
        "label": preferred.label,
        "content": preferred.content,
        "rationale": preferred.rationale,
        "type": preferred.type,
        "priority": preferred.priority,
    }


def _build_suggestions_for_move(decision: TurnDecision) -> list[Suggestion]:
    if decision.next_move == "force_rank_or_choose":
        return [
            Suggestion(
                type="direction",
                label="先聚焦一类最具体的目标用户",
                content="从最容易触达的一类用户开始描述",
                rationale="用户范围过宽会导致验证发散",
                priority=2,
            ),
            Suggestion(
                type="direction",
                label="先锁定一个最痛的问题场景",
                content="描述一次最近发生的真实场景",
                rationale="具体场景能逼出优先级",
                priority=3,
            ),
            Suggestion(
                type="recommendation",
                label="先在用户或问题里二选一做主线",
                content="只选一个主线方向先推进",
                rationale="先做取舍才能加速收敛",
                priority=1,
            ),
        ]
    if decision.next_move == "probe_for_specificity":
        return [
            Suggestion(
                type="recommendation",
                label="先把一句话说具体",
                content="用一个真实场景和角色把描述补全",
                rationale="具体场景能让需求收敛",
                priority=1,
            ),
            Suggestion(
                type="direction",
                label="给出最近一次真实发生的例子",
                content="说明时间、地点、触发原因",
                rationale="例子越清晰，下一步越明确",
                priority=2,
            ),
            Suggestion(
                type="tradeoff",
                label="从频率或成本先选一个指标",
                content="明确到底是频率高还是成本高更优先",
                rationale="指标会决定追问方向",
                priority=3,
            ),
        ]
    if decision.next_move == "challenge_and_reframe":
        return [
            Suggestion(
                type="recommendation",
                label="先把问题重新说清楚",
                content="用一句话描述最痛的问题",
                rationale="问题清晰后方案选择才有意义",
                priority=1,
            ),
            Suggestion(
                type="direction",
                label="用真实场景复述问题",
                content="描述用户在什么场景下因什么受阻",
                rationale="真实场景能避免泛泛而谈",
                priority=2,
            ),
            Suggestion(
                type="warning",
                label="避免先谈方案细节",
                content="先确认问题再展开方案细节",
                rationale="先谈方案容易跑偏问题本质",
                priority=3,
            ),
        ]
    if decision.next_move == "assume_and_advance":
        return [
            Suggestion(
                type="recommendation",
                label="先基于一个假设推进",
                content="把当前理解写成一句可验证的话",
                rationale="假设清晰才能快速验证",
                priority=1,
            ),
            Suggestion(
                type="direction",
                label="列出两个备选方向并打分",
                content="按验证成本与价值排序",
                rationale="并列方向会拖慢推进",
                priority=2,
            ),
            Suggestion(
                type="tradeoff",
                label="先验证频率还是付费意愿",
                content="明确当前最想验证的指标",
                rationale="指标决定接下来的追问方向",
                priority=3,
            ),
        ]
    if decision.next_move == "summarize_and_confirm":
        return [
            Suggestion(
                type="recommendation",
                label="先确认当前共识",
                content="核对目标用户、问题与方案是否准确",
                rationale="确认共识后才能进入下一步",
                priority=1,
            ),
            Suggestion(
                type="direction",
                label="补齐一个最大缺口",
                content="挑一个最影响推进的缺口补齐",
                rationale="补齐关键缺口能减少返工",
                priority=2,
            ),
            Suggestion(
                type="tradeoff",
                label="决定继续澄清还是开始收敛方案",
                content="明确下一步是追问还是选方向",
                rationale="明确推进策略能避免犹豫",
                priority=3,
            ),
        ]
    return [
        Suggestion(
            type="recommendation",
            label="先补充最具体的场景",
            content="给出一次最近发生的例子",
            rationale="具体例子能帮助快速收敛",
            priority=1,
        ),
        Suggestion(
            type="direction",
            label="明确最优先验证的指标",
            content="从频率、成本或价值里先选一个",
            rationale="指标清晰才能决定追问方向",
            priority=2,
        ),
        Suggestion(
            type="tradeoff",
            label="说明最重要的限制条件",
            content="时间、人力或预算的硬约束",
            rationale="限制条件会影响方案取舍",
            priority=3,
        ),
    ]
