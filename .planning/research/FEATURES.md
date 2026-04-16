# Feature Research

**Domain:** 面向独立开发者的 AI 产品脑暴 / PRD copilot
**Researched:** 2026-04-16
**Confidence:** MEDIUM

## Feature Landscape

### Table Stakes (Users Expect These)

用户默认会认为这些能力存在。缺少后，产品会被理解成“只是一个包装过的聊天框”。

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| 模糊输入转结构化首稿 | 竞品普遍支持从一句想法、会议纪要或提示词直接生成 PRD/one-pager/规格草稿；用户不会接受从空白页开始 | MEDIUM | 需要把输入压成固定骨架，至少覆盖问题、目标用户、方案、范围、成功指标 |
| 引导式追问与上下文澄清 | 强产品定义体验不是一次生成，而是通过追问把背景、约束、目标补齐 | MEDIUM | 追问不能泛泛而谈，要围绕“用户/问题/方案/边界/证据”推进 |
| 可编辑的结构化 PRD 视图 | 用户期望 AI 产出不是一次性回答，而是可回看、可修改、可继续迭代的文档 | MEDIUM | 需要章节化、块级更新、版本留痕，避免整篇重写造成失控 |
| 模板化输出与稳定框架 | ChatPRD、Notion、Confluence 都强调模板与一致结构；用户需要“知道结果会长什么样” | LOW | 对独立开发者应提供少量强约束模板，而不是大而全模板市场 |
| 单一事实源与会话/文档持久化 | 产品定义天然跨多轮；用户希望会话、草稿、附件、结论能持续存在 | MEDIUM | 必须支持继续会话、恢复上下文、引用已有内容，不然很难形成收敛链路 |
| 导出与外部协作交付 | 竞品普遍支持导出到 Notion、Confluence、Markdown 或任务工具；用户不会接受内容被锁死在产品里 | MEDIUM | 对 indie 用户，优先 Markdown / 可复制 PRD / 后续开发提示，而非重型企业集成 |
| 基础评审维度：目标、范围、成功指标 | 官方 PRD 模板普遍要求 objectives、assumptions、options、success metrics、out-of-scope | LOW | 这是 PRD 最低质量线，不做会导致文档看似完整但不可执行 |

### Differentiators (Competitive Advantage)

这些能力不是所有产品都做深，但一旦做好，会直接提升“从模糊想法到可执行定义”的成功率。

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 矛盾检测与假设揭示 | 用户最常见的问题不是“没有点子”，而是点子里混着冲突、跳步和未说出的假设；主动指出这些问题，价值高于继续陪聊 | HIGH | 需要检测目标冲突、用户段不一致、范围与资源不匹配、指标与方案脱节 |
| 收敛引擎（何时发散、何时收紧） | 强体验不是一直追问，也不是立刻写文档，而是知道何时给选项、何时深挖、何时开始定稿 | HIGH | 建议显式维护探索态、聚焦态、定稿态，并允许回退 |
| 选项驱动式提示（反应式而非纯开放问答） | 模糊想法用户往往“有感觉但说不清”；给出 2-4 个可反应方向，比要求用户自己组织语言更有效 | MEDIUM | 适合问题陈述、目标用户、核心工作流、商业模式、MVP 边界等关键节点 |
| 未知项 / 风险 / 待验证清单 | 强产品定义不应假装已经想清楚；把“还不知道什么”显式化，能避免 PRD 伪完整 | MEDIUM | 输出中应保留 open questions、risks、assumptions to validate，而不是只给确定性语气 |
| PRD 质量评分与定向补强 | ChatPRD 已把 gap analysis 和 review coach 产品化；若能结合 indie 场景给出“最缺哪一节、为何影响实现”，会明显提升可执行性 | HIGH | 评分必须可解释，不能只给笼统分数；建议按问题定义、用户清晰度、范围边界、验证路径拆分 |
| 从产品想法到执行前工件的桥接 | 对独立开发者，PRD 的下游往往不是大型团队评审，而是直接进入原型或编码；能一键生成 build brief / MVP scope / AI coding prompt 很有吸引力 | MEDIUM | 这类桥接应在 PRD 足够稳定后触发，否则会放大前期模糊性 |
| “独立开发者默认值”模式 | indie 用户通常缺少研究素材、团队分工和成熟 PM 术语；系统若能默认轻量化结构、少术语、强例子，会比企业 PM 导向产品更贴合 | MEDIUM | 例如自动把 enterprise 字段折叠为“是否需要”“先不考虑”，减少表达负担 |

### Anti-Features (Commonly Requested, Often Problematic)

这些功能表面上很诱人，但对“模糊想法压实”主链路帮助有限，反而容易拖慢产品判断与路线收敛。

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| 通用闲聊人格 / 陪聊增强 | 用户会把“会聊天”误认为“会帮我想清楚” | 会稀释引导强度，让系统长期停留在发散态，产出变得好看但不可执行 | 保留自然对话语气，但把每轮都绑定到澄清、分歧、取舍或沉淀目标 |
| 大而全模板市场 | 看起来“覆盖更多场景” | 模糊想法用户面对大量模板会更难起步，且容易把注意力放在格式而不是思考质量 | 只保留少量高信号入口：想法澄清、PRD 初稿、MVP scope、验证计划 |
| 过早生成 Jira/Linear 大量任务 | 很容易被认为“更落地” | 在需求尚未收敛前生成任务，会把模糊内容固化成伪精确执行项，后续返工高 | 先输出 scope、用户流、验收方向；待 PRD 稳定后再生成 tickets |
| 重型多人协同与审批流 | 企业软件常见能力，容易被拿来当“成熟度”指标 | 对 indie 主用户不是关键路径，会显著增加界面与状态复杂度 | 先做轻量分享、导出、评论锚点；复杂协作延后 |
| 自动补全一切、隐藏不确定性 | 用户喜欢“一键完成”叙事 | 会制造错误确定感，尤其在目标用户、成功指标、市场前提不清时最危险 | 明确区分“已确认”“推断”“待验证”，把不确定性可视化 |

## Feature Dependencies

```text
模糊输入转结构化首稿
    └──requires──> 模板化输出与稳定框架
                           └──requires──> 基础评审维度：目标、范围、成功指标

引导式追问与上下文澄清
    └──enables──> 选项驱动式提示
                       └──enables──> 收敛引擎（何时发散、何时收紧）

引导式追问与上下文澄清
    └──enables──> 矛盾检测与假设揭示
                       └──enables──> PRD 质量评分与定向补强

单一事实源与会话/文档持久化
    └──requires──> 可编辑的结构化 PRD 视图
                       └──enables──> 导出与外部协作交付

收敛引擎（何时发散、何时收紧）
    └──enables──> 从产品想法到执行前工件的桥接

自动补全一切、隐藏不确定性
    ──conflicts──> 未知项 / 风险 / 待验证清单

过早生成 Jira/Linear 大量任务
    ──conflicts──> 收敛引擎（何时发散、何时收紧）
```

### Dependency Notes

- **模糊输入转结构化首稿 requires 模板化输出与稳定框架：** 没有稳定骨架，AI 只能产出“像文档的长回复”，很难持续迭代。
- **引导式追问与上下文澄清 enables 选项驱动式提示：** 选项不是静态模板，而是基于当前语境的下一步建议。
- **引导式追问与上下文澄清 enables 矛盾检测与假设揭示：** 只有先收集到目标、用户、边界、资源等信息，系统才有检测矛盾的条件。
- **矛盾检测与假设揭示 enables PRD 质量评分与定向补强：** 没有结构化缺口识别，评分会退化成主观“写得好不好”。
- **单一事实源与会话/文档持久化 requires 可编辑的结构化 PRD 视图：** 持久化不只是存聊天记录，还要存可复用的结构化结论。
- **收敛引擎 enables 从产品想法到执行前工件的桥接：** 如果未判断“已经足够清晰”，后续原型提示和 build brief 只会把错误放大。
- **自动补全一切 conflicts 未知项 / 风险 / 待验证清单：** 一个强调完整，一个强调诚实暴露不确定性，两者不能同时作为默认体验。
- **过早生成 Jira/Linear 大量任务 conflicts 收敛引擎：** 一个推动 premature convergence，一个要求先完成必要澄清。

## MVP Definition

### Launch With (v1)

最小可行版本应验证：系统是否真的能帮助“有模糊想法但说不清”的独立开发者更快收敛。

- [ ] 模糊输入转结构化首稿 — 这是进入价值感知的第一步，必须在几分钟内让用户看到“想法被压实”
- [ ] 引导式追问与上下文澄清 — 没有这一层，就只是一次性生成器，不是 copilot
- [ ] 选项驱动式提示 — 这是面向模糊想法用户的关键可用性能力
- [ ] 可编辑的结构化 PRD 视图 — 用户需要看到内容是如何被逐步收敛的
- [ ] 基础评审维度：目标、范围、成功指标 — 没有这些，PRD 对后续执行价值很低
- [ ] 未知项 / 风险 / 待验证清单 — 防止首版产品输出“伪完整 PRD”

### Add After Validation (v1.x)

- [ ] 矛盾检测与假设揭示 — 当基础引导链路稳定后加入，可显著提升“想清楚”的质量
- [ ] 收敛引擎（何时发散、何时收紧） — 在有足够行为数据后更容易做准，而不是拍脑袋定节奏
- [ ] 导出与外部协作交付 — 当用户开始稳定产出可用文档后，再补导出链路最有价值
- [ ] PRD 质量评分与定向补强 — 适合作为 second-order productization，用来提高完成率和复用率

### Future Consideration (v2+)

- [ ] 从产品想法到执行前工件的桥接 — 价值高，但依赖前面收敛质量足够稳定
- [ ] “独立开发者默认值”模式 — 很值得做，但应在观察真实用户语言习惯后再固化
- [ ] 轻量外部上下文导入（如现有笔记/链接/代码仓库摘要） — 有潜力提升 grounding，但不是首发必须项

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| 模糊输入转结构化首稿 | HIGH | MEDIUM | P1 |
| 引导式追问与上下文澄清 | HIGH | MEDIUM | P1 |
| 选项驱动式提示 | HIGH | MEDIUM | P1 |
| 可编辑的结构化 PRD 视图 | HIGH | MEDIUM | P1 |
| 基础评审维度：目标、范围、成功指标 | HIGH | LOW | P1 |
| 未知项 / 风险 / 待验证清单 | HIGH | MEDIUM | P1 |
| 矛盾检测与假设揭示 | HIGH | HIGH | P2 |
| 收敛引擎（何时发散、何时收紧） | HIGH | HIGH | P2 |
| 导出与外部协作交付 | MEDIUM | MEDIUM | P2 |
| PRD 质量评分与定向补强 | MEDIUM | HIGH | P2 |
| 从产品想法到执行前工件的桥接 | MEDIUM | MEDIUM | P3 |
| “独立开发者默认值”模式 | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: 首发必须有，否则难以验证核心价值
- P2: 首发后应尽快补齐，直接提升收敛质量和交付价值
- P3: 有潜力，但应在核心链路稳定后再做

## Competitor Feature Analysis

| Feature | Competitor A | Competitor B | Our Approach |
|---------|--------------|--------------|--------------|
| 从模糊输入起草 PRD | ChatPRD 强，支持从 prompt、meeting notes、已有文档生成 PRD | Notion/Confluence 更偏文档容器和模板，起草能力有但不是核心引导体验 | 保留快速首稿，但把重点放在“生成后如何继续压实” |
| 模板与结构化框架 | ChatPRD 模板多、覆盖 PRD/strategy/GTM/testing | Notion/Confluence 强在模板化和单一事实源 | 采用少而强的模板集，优先服务 indie 模糊想法场景 |
| 追问与脑暴推进 | Miro 强在发散、替代方案、后续问题提示 | ChatPRD 提供 brainstorm/review/write 多工作流 | 把“追问 + 选项 + 收敛判断”做成同一条连续体验，而非分散模式 |
| 缺口/问题识别 | ChatPRD 已显式强调 strategic gap analysis、questioning assumptions、edge case detection | Notion/Confluence 更依赖用户自己审阅模板项 | 重点强化矛盾检测、隐含假设揭示、未知项显式化 |
| 下游交付 | ChatPRD 强集成，导出到 Linear/Notion/Confluence，并可生成原型 | Notion/Confluence 强在团队协作与知识库沉淀 | 首阶段优先轻导出与 build-ready 文本，不急于做重型团队集成 |

## Sources

- ChatPRD 首页与产品页：PRD 生成、gap analysis、assumption questioning、integrations、versioning
  - https://www.chatprd.ai/
  - https://www.chatprd.ai/product/use-cases/product-managers
- ChatPRD 模板文档：PRD、技术设计、用户画像、旅程图、Founding Hypothesis、PRD for v0.dev
  - https://www.chatprd.ai/docs/included-templates
- Atlassian Confluence PRD 模板：objectives、assumptions、options、supporting docs、open questions、out-of-scope
  - https://www.atlassian.com/software/confluence/templates/product-requirements
- Notion PRD 场景页：single source of truth、template、feedback、problem/proposal/plan、context consolidation
  - https://www.notion.com/use-case/product-requirements-document-prd
  - https://www.notion.com/help/guides/using-notion-for-product-requirement-documents
- Miro AI ideation prompts：feature ideas、follow-up questions、alternative approaches、idea expansion
  - https://miro.com/ai/prompts/brainstorming-prompts/
  - https://help.miro.com/hc/en-us/articles/30795865056402-Content-generation-and-ideation-starter-prompts
- 研究参考：LLM 在发散与收敛两阶段都能提供支持，但也存在设计固着风险；因此“多方案探索 + 显式收敛”比纯一次生成更合理
  - https://arxiv.org/abs/2402.14978
  - https://arxiv.org/abs/2403.11164
  - https://arxiv.org/abs/2403.13002

## Confidence Notes

- **HIGH:** 模板化、PRD 结构、导出、单一事实源、基于已有文档生成草稿，这些已被官方产品页面明确支持。
- **MEDIUM:** “对独立开发者最有价值的差异项”带有目标用户推断，但与项目 `PROJECT.md` 的用户画像一致。
- **MEDIUM:** Anti-features 主要来自竞品能力边界、研究结论与本项目核心价值的逆向推导，适合作为路线约束，不宜当成通用真理。

---
*Feature research for: AI brainstorming / PRD copilot for indie developers*
*Researched: 2026-04-16*
