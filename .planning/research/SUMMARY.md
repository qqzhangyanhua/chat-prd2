# Project Research Summary

**Project:** AI Brainstorming PRD Copilot
**Domain:** 面向独立开发者的 AI brainstorming / PRD 收敛工作台增强
**Researched:** 2026-04-16
**Confidence:** HIGH

## Executive Summary

这不是一个“更会聊天的 AI 助手”，而是一个建立在现有工作台之上的需求澄清与 PRD 收敛系统。研究结果高度一致：成熟做法不是继续堆自由对话能力，而是把每轮输入先转成结构化判断，再用显式状态推进澄清、发现矛盾、控制收敛，最后以分段补丁而不是整篇重写的方式形成 PRD。对本项目而言，正确方向是保留现有 `Next.js + FastAPI + PostgreSQL` 壳，把产品能力重心放到 typed policy engine、issue ledger、结构化 PRD patch、决策日志与评测闭环。

推荐路线很明确：先固化状态与协议，再补澄清与选项式引导，然后做矛盾/缺口检测，再实现收敛闸门与 PRD 编排，最后补观测、评测与导出桥接。这样做既符合现有代码边界，也符合功能依赖关系，因为“更聪明的问法”并不能替代“可追溯的断言层”和“可验证的收敛条件”。

最大的风险同样很集中：一是过早把模糊想法写死成确定需求，二是只会追问不会收束，三是让前端或自由文本隐式承载策略。缓解方式不是继续调大 prompt，而是建立 confirmed / inferred / missing / contradiction 的状态模型、按断言存证据来源、把阶段切换做成显式 gate，并用回放与评测验证“系统是否真的减少歧义并提升 PRD 可执行性”。

## Key Findings

### Recommended Stack

研究结论不是换栈，而是在现有技术栈上补关键基础设施。前端继续使用 Next.js 15 + React 19 工作台，后端继续以 FastAPI + Pydantic 2 + SQLAlchemy + PostgreSQL 为主骨架；真正需要新增的是结构化输出、状态持久化、语义召回与观测评测工具。核心原则是“关系数据做真相源，向量检索只做会话内 recall，策略由后端决定，前端只渲染结构化动作”。

**Core technologies:**
- Next.js 15.x + React 19.x：继续承载现有工作台 UI 与流式交互，避免为本轮目标做无关升级。
- FastAPI 0.135.3 + Pydantic 2.13.1：承载回合决策、结构化输出和流式 API，是 typed agent 服务层的稳定基础。
- PostgreSQL 17/18 + pgvector：保存消息、断言、issue ledger、PRD snapshot，并提供会话内语义召回。
- SQLAlchemy 2.0.49 + psycopg 3.3.3：维持事务边界和 typed 数据访问，支撑回放、版本与审计。
- OpenAI Python SDK 2.32.0：优先使用原生 structured outputs / Pydantic parse，避免脆弱 JSON 提示词。
- LiteLLM 1.83.8：统一模型网关、fallback 和预算控制，避免业务层散落多家模型兼容。
- Langfuse 4.2.0 + Promptfoo 4.3.6 + OpenTelemetry 1.41.0：建立 prompt 版本、回放、评测与系统级 tracing 闭环。

### Expected Features

功能研究给出的优先级很稳定：首发必须先证明“能把模糊想法压实”，而不是证明“能做很多下游自动化”。因此 v1 必须覆盖首稿生成、引导式追问、选项驱动、结构化 PRD 视图、基础评审维度，以及未知项/风险显式化。矛盾检测、收敛引擎和质量评分属于直接增强核心价值的第二层能力，应尽快跟进；任务生成、重型协作和大而全模板则应明确延后。

**Must have (table stakes):**
- 模糊输入转结构化首稿：让用户快速看到想法被压成 PRD 骨架。
- 引导式追问与上下文澄清：把对话从陪聊拉回用户、问题、方案、边界和证据。
- 选项驱动式提示：降低“脑中有想法但不会表达”的阻力。
- 可编辑的结构化 PRD 视图：支持块级更新、持续收敛和版本留痕。
- 基础评审维度：至少覆盖目标、范围、成功指标。
- 未知项 / 风险 / 待验证清单：避免输出伪完整 PRD。

**Should have (competitive):**
- 矛盾检测与假设揭示：把冲突与隐含前提变成可行动诊断，而不是普通摘要。
- 收敛引擎：显式决定何时探索、何时比较、何时确认。
- 导出与外部协作交付：优先 Markdown / 可复制 PRD / build brief。
- PRD 质量评分与定向补强：按缺口类型补洞，而不是给笼统分数。

**Defer (v2+):**
- 从产品想法到执行前工件的桥接：依赖前序收敛质量足够稳定。
- “独立开发者默认值”模式：需要真实用户行为数据后再固化。
- 轻量外部上下文导入：有价值，但不是首发必要条件。
- 重型多人协作、审批流、任务批量生成：与当前核心价值不匹配。

### Architecture Approach

架构研究建议沿用现有单体前后端，但把职责切得更清楚：前端维护事件归并后的单一真相源，后端负责 API 编排与事务，智能决策集中在独立 turn intelligence 层，PRD 与运行状态分成双轨状态，模型调用走统一网关，评估和观测独立沉淀。关键模式是 `TurnDecision` 决策包络、运行态与 PRD 草稿双轨状态、以及可中断的收敛闸门。

**Major components:**
1. Web Workspace + Store：消费结构化事件，渲染对话、引导卡、确认卡与 PRD 面板。
2. API / Service Orchestration：处理鉴权、流式协议、事务边界、持久化顺序。
3. Turn Intelligence Layer：执行抽取、矛盾/缺口判断、收敛策略、回复规划与 PRD patch 生成。
4. Persistence Layer：分别保存 messages、assertions/issues、turn decisions、state snapshots、PRD snapshots。
5. Model Gateway + Observability：统一结构化输出、provider 适配、trace、eval 与 replay。

### Critical Pitfalls

1. **过早把模糊想法写死为确定需求** — 通过 confirmed / inferred / missing 分层、证据绑定和严格 PRD patch 机制避免未确认信息进入主文档。
2. **矛盾检测退化成普通摘要** — 关键字段必须结构化成断言，并输出冲突两端、来源、影响与下一步问题。
3. **只会追问，不会收敛** — 为 `clarify / choose / converge / confirm` 建立明确切换条件和 checkpoint。
4. **选项式引导绑架用户** — 所有选项都保留“都不对，我来补充/改写”入口，并把高默认接受率视为风险信号。
5. **未知项被静默补全、来源不可追溯** — PRD 必须显示 `confirmed / inferred / missing`，任一断言都能回溯到来源轮次和确认状态。

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: 状态契约与证据层
**Rationale:** 所有后续能力都依赖可追溯的断言层和稳定协议；没有这层，矛盾检测、收敛控制和 PRD patch 都会失真。  
**Delivers:** `TurnDecision`、`StatePatch`、`PrdPatch`、assertion / issue / snapshot schema，及来源追溯字段。  
**Addresses:** 单一事实源与会话/文档持久化、可编辑结构化 PRD 视图、未知项显式化。  
**Avoids:** 过早写死需求、未知项被静默补全、无来源可追溯。

### Phase 2: 澄清策略与选项式引导
**Rationale:** v1 核心价值首先体现在“用户能被有效带着想清楚”，而不是先做复杂诊断。  
**Delivers:** 引导式追问策略、选项驱动 UI contract、阶段性 checkpoint、疲劳时的收束 fallback。  
**Uses:** FastAPI 服务层、前端 workspace store、结构化 `assistant_action`。  
**Implements:** Turn intelligence 中的 reply planner 与 guidance contract。  
**Avoids:** 只会追问不收敛、选项绑架用户、前端自行猜阶段。

### Phase 3: 矛盾与缺口检测引擎
**Rationale:** 这是本项目与普通 PRD 生成器拉开差距的关键点，应在协议和基本引导稳定后落地。  
**Delivers:** 结构化断言对比、规则+LLM 混合检测、冲突解释、缺口 issue ledger。  
**Addresses:** 矛盾检测与假设揭示、未知项 / 风险 / 待验证清单。  
**Avoids:** 检测只停留在摘要层、PRD 混入相互排斥约束。

### Phase 4: 收敛闸门与 PRD 编排
**Rationale:** 当检测能力具备后，才能可靠判断何时开始收束并把断言映射成可确认 PRD。  
**Delivers:** `clarify → choose → converge → confirm` 策略切换、finalize readiness、section merge、confirmed/inferred/missing 状态导出。  
**Uses:** Pydantic schema、PostgreSQL snapshot、结构化 patch pipeline。  
**Implements:** Interruptible convergence gate 与 PRD section-based drafting。  
**Avoids:** PRD 只是大作文、导出时重新让模型编事实、过度追问。

### Phase 5: 评测观测与导出桥接
**Rationale:** 没有观测和回归，就无法判断系统是真的更会收敛，还是只是更会聊天。  
**Delivers:** Langfuse traces、Promptfoo 回归集、领域指标看板、Markdown / build brief 导出。  
**Addresses:** 导出与外部协作交付、PRD 质量评分与定向补强、后续执行前工件桥接。  
**Avoids:** 用聊天指标替代需求质量指标、长会话漂移不可见、导出锁死在产品内。

### Phase Ordering Rationale

- 先做 Phase 1，是因为 features、architecture、pitfalls 三份研究都把“结构化状态与证据层”视为所有能力的前提。
- Phase 2 早于 Phase 3，是因为用户首先感知的是引导质量；同时基本澄清流为后续矛盾检测提供必要上下文。
- Phase 3 早于 Phase 4，是因为收敛判断必须建立在“知道还有哪些缺口和冲突”之上，否则 finalize gate 不可信。
- Phase 4 才开始把 PRD 做深，是为了避免“整篇重写”反复掩盖真实问题。
- Phase 5 收尾，是因为观测、评分、导出桥接高度依赖前四阶段已经形成稳定协议和状态面。

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3：** 混合式矛盾检测规则、断言分类和误报控制需要更细的实现研究与样例集设计。
- **Phase 5：** 评测指标、judge 规则、导出到 build brief 的质量门槛需要额外验证。
- **Phase 4：** finalize readiness 阈值和 section merge 规则需要基于真实会话样本校准。

Phases with standard patterns (skip research-phase):
- **Phase 1：** schema、snapshot、event contract、provenance 存储是成熟工程模式，可直接规划实施。
- **Phase 2：** 基础选项式引导与 checkpoint UI 在现有工作台架构上有清晰落点，主要是产品约束不是技术未知。

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | 主要来自官方文档、版本信息与现有代码边界，结论稳定且工程约束明确。 |
| Features | MEDIUM | 竞品与模板分析较充分，但“indie 用户最重视什么”仍含目标用户推断。 |
| Architecture | HIGH | 同时参考了现有代码结构与成熟 agent/workflow 模式，边界建议可直接落地。 |
| Pitfalls | MEDIUM | 来源涵盖论文、工业经验与逆向约束，适合作为路线护栏，但部分风险权重需用真实用户数据校准。 |

**Overall confidence:** HIGH

### Gaps to Address

- **断言模型粒度：** 需在规划阶段明确断言类型、字段规范和最小可用 provenance 结构，避免 Phase 1 过宽。
- **收敛阈值：** “何时足够清晰可以 finalize” 仍需基于真实会话样本做规则校准。
- **误报与过度引导平衡：** Phase 3 和 Phase 2 会相互影响，需要用回归集评估“矛盾提示是否打断用户表达”。
- **导出桥接质量门槛：** build brief / coding prompt 何时可生成，必须绑定 confirmed coverage，而不能仅凭字数或对话轮数。

## Sources

### Primary (HIGH confidence)
- [STACK.md](/Users/zhangyanhua/AI/chat-prd2/.planning/research/STACK.md) — 官方文档与版本验证后的推荐栈、实现路径与禁用项。
- [ARCHITECTURE.md](/Users/zhangyanhua/AI/chat-prd2/.planning/research/ARCHITECTURE.md) — 结合现有代码与标准模式得出的组件边界、数据流和构建顺序。
- OpenAI、FastAPI、Pydantic、PostgreSQL、pgvector、Langfuse 官方文档与版本源 — 用于验证结构化输出、存储与观测能力。

### Secondary (MEDIUM confidence)
- [FEATURES.md](/Users/zhangyanhua/AI/chat-prd2/.planning/research/FEATURES.md) — 基于 ChatPRD、Notion、Confluence、Miro 与相关论文归纳的功能优先级。
- [PITFALLS.md](/Users/zhangyanhua/AI/chat-prd2/.planning/research/PITFALLS.md) — 基于 requirements/LLM 研究与工业经验提炼的风险模式。
- ChatPRD、Notion、Confluence、Miro 官方产品页 — 用于校验 table stakes 与差异化方向。

### Tertiary (LOW confidence)
- 关于“独立开发者默认值模式”“桥接到编码 prompt 的最佳时机”等判断，当前仍主要是基于研究综合推断，需在后续真实用户数据中验证。

---
*Research completed: 2026-04-16*
*Ready for roadmap: yes*
