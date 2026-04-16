# Pitfalls Research

**Domain:** 面向独立开发者的 AI brainstorming / PRD-copilot 产品（既有 AI ideation app 的后续增强）
**Researched:** 2026-04-16
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: 过早把模糊想法“写死”为确定需求

**What goes wrong:**
系统在信息不足时直接输出方案、用户画像或 PRD 结论，把“待探索的假设”伪装成“已确认的需求”。后续对话即使出现新信息，也很难把方向拉回来，最终形成一份结构完整但方向错误的 PRD。

**Why it happens:**
多轮对话型 LLM 容易在早期回合做假设并提前产出最终答案；一旦走偏，后续会持续依赖错误前提。产品侧又常把“输出完整 PRD”当成主要体验目标，导致系统奖励“快收敛”而不是“先澄清”。

**How to avoid:**
- 把对话状态显式分层为 `已确认`、`候选假设`、`待澄清问题`、`已发现矛盾`，禁止直接把未确认内容写入最终 PRD 主体。
- 在 agent 策略中加入“是否应该先问澄清问题”的门槛，优先判断是否缺关键前提，再决定是否生成结论。
- PRD 生成采用“证据驱动填槽”而不是一次性整篇生成；每个段落都应绑定来源片段或确认轮次。
- 在 UI 中把“当前仍不确定什么”单独展示，避免用户误以为系统已经理解完整。

**Warning signs:**
- 第 2～4 轮就开始稳定输出功能列表、路线图或技术方案。
- 同一主题后续出现用户纠正，但摘要/PRD 没有明显回滚。
- 系统很少提出澄清问题，却频繁给出确定性表达，如“目标用户就是…”“核心场景是…”。

**Phase to address:**
Phase 1「对话状态模型与证据分层」+ Phase 2「澄清策略与引导节奏」

---

### Pitfall 2: 把“矛盾检测”做成普通摘要，而不是可执行诊断

**What goes wrong:**
系统能复述用户说过什么，却识别不出“目标用户是独立开发者，但又要求企业级审批流”这类跨轮次冲突；或者只是提示“可能有矛盾”，却说不清冲突点、影响范围和待决策问题。

**Why it happens:**
纯 LLM 摘要擅长语言压缩，不擅长稳定维护结构化约束。研究也显示，纯 LLM 的矛盾检测在要求较严的场景下明显不如“规则/形式化 + LLM”的混合方法；同时真实工业需求里的歧义检测效果高度依赖示例与解释增强。

**How to avoid:**
- 不要只保留一段滚动 summary；要把关键需求拆成结构化断言，如用户、问题、目标、边界、非目标、约束、依赖。
- 对关键字段做成对比检查：目标冲突、范围冲突、时间冲突、角色冲突、成功指标冲突。
- 冲突输出必须包含四部分：冲突的两端、证据来源、为什么冲突、建议澄清问题。
- 对高价值矛盾使用混合检测：规则/模式匹配先召回，LLM 再负责解释与追问文案。

**Warning signs:**
- 系统只能说“这里可能不一致”，但无法指出是哪两句话冲突。
- 用户自己能看出冲突，系统却继续生成统一叙事。
- 生成的 PRD 把相互排斥的约束并列写入“需求”章节。

**Phase to address:**
Phase 3「矛盾与缺口检测引擎」

---

### Pitfall 3: 只会追问，不会控制收敛

**What goes wrong:**
产品把“多问问题”误当成“引导质量高”。结果用户被持续追问，系统迟迟不给阶段性收束、候选方案或临时结论，最后要么放弃，要么得到一堆聊天记录而不是 PRD。

**Why it happens:**
模糊需求往往确实需要多轮澄清，但“需要多轮”不等于“无限追问”。学术研究已明确指出，多轮交互能降低歧义和不完整性，但当前 AI-based elicitation 的核心挑战正是缺少迭代 refinement、幻觉控制和 semantic convergence。

**How to avoid:**
- 定义显式收敛条件，例如：核心用户、核心问题、核心方案、边界、成功指标中至少 4/5 已确认，且关键矛盾已处理。
- 每轮输出都要在“继续探索 / 局部收束 / 进入 PRD 草稿”三种动作中二选一或三选一，而不是默认继续问。
- 采用阶段性 checkpoint：每 3～5 轮产出一次“当前共识 + 未决问题 + 下一步建议”。
- 当用户表现出疲劳或回答越来越短时，自动切到“选项式收束”而不是开放式继续深挖。

**Warning signs:**
- 对话超过 10 轮仍没有稳定的中间产物。
- 用户连续两轮只回“都可以”“你建议下”，系统仍继续开放式提问。
- PRD 只在对话最后一次性生成，中间没有任何收束节点。

**Phase to address:**
Phase 2「澄清策略与引导节奏」+ Phase 4「收敛控制与 PRD 编排」

---

### Pitfall 4: 选项式引导过强，导致用户被系统默认答案牵着走

**What goes wrong:**
为了降低表达门槛，系统大量提供选项，但这些选项其实把用户引到模型最常见、最模板化的答案上。最终产物“看起来合理”，却越来越不像用户原本的想法。

**Why it happens:**
LLM 在创意任务中存在明显输出同质化风险；如果产品只提供少数预设选项，用户很容易发生 automation bias，接受一个“够像样”的默认答案而不再主动修正。

**How to avoid:**
- 所有选项都必须附带“为什么现在给你这几个选项”的依据，并永远保留“都不对，我重写/补充”入口。
- 选项用于压缩表达成本，不用于替代判断；对关键字段要求用户确认或改写，而不是只点选。
- 对高影响字段采用“选项 + 自由补充 + 反例追问”三联设计。
- 记录用户是“主动选择”还是“被动接受默认”，把高默认接受率视为风险指标而非成功指标。

**Warning signs:**
- 不同用户最后得到高度相似的目标用户、功能优先级和 PRD 结构。
- “接受建议”点击率很高，但后续导出/继续编辑率低。
- 用户很少修改系统给的措辞，PRD 语言风格高度模板化。

**Phase to address:**
Phase 2「选项式引导设计」+ Phase 5「质量评估与人机协作校准」

---

### Pitfall 5: 没有把“未知项”和“缺口”显式产出

**What goes wrong:**
系统把信息缺口静默补全，最后产物表面完整，但没有告诉用户哪些内容其实尚未确认、哪些是推断、哪些需要用户补证据。这样最容易让独立开发者误把草稿当真需求。

**Why it happens:**
很多产品把“完整度”当成功指标，导致模型倾向于填满模板。可一旦输入存在 ambiguity 或 incompleteness，最稳妥的系统行为应该是暴露未知，而不是伪造完整。

**How to avoid:**
- PRD 中单独保留“未决问题 / 假设 / 风险”章节，且不允许为空。
- 每个核心章节都显示确认度，例如 `confirmed / inferred / missing`。
- 对缺关键信息的字段，不生成“像答案的句子”，而生成“需要确认的问题”。
- 导出时提供“严格模式”：未确认字段以占位提醒保留，不自动润色成定稿语气。

**Warning signs:**
- PRD 读起来像已经评审通过，但系统无法指出哪几条是推断来的。
- 所有字段都被填满，几乎没有“待确认”状态。
- 用户在导出后才发现关键问题根本没讨论，例如定价、分发、非目标用户。

**Phase to address:**
Phase 1「证据/确认状态模型」+ Phase 4「PRD 输出契约」

---

### Pitfall 6: 缺少来源可追溯性，导致修正时无法回滚

**What goes wrong:**
摘要、状态快照和 PRD 会不断演化，但每一条结论来自哪一轮、哪一段输入、是否经过用户确认都不可追溯。这样一旦发现理解错了，只能整段重写，而不是精确修正。

**Why it happens:**
很多 AI copilot 产品只维护“最新摘要”，不维护 assertion-level provenance。对于持续收敛产品，这会直接破坏纠错能力。

**How to avoid:**
- 给关键断言保存 `source_turn_ids`、`speaker`、`confirmation_status`、`superseded_by`。
- 摘要更新采用增量 merge，而不是整段覆盖。
- UI 中支持查看“这条 PRD 内容来自哪里”，并允许按断言撤销或重开。
- 冲突检测、导出、恢复会话都统一基于同一套断言层，而不是各自维护文本副本。

**Warning signs:**
- 用户问“这句话哪来的？”系统答不上来。
- 修一个字段会连带改坏整段不相关内容。
- 同一会话多次总结后，早期关键约束消失。

**Phase to address:**
Phase 1「断言层与快照溯源」

---

### Pitfall 7: 把 PRD 生成做成一次性文案整理，而不是逐段验证编排

**What goes wrong:**
产品把 PRD 当作最后一步“大作文生成”。结果文档可读性不错，但与前面对话中的共识、矛盾和边界并不严格对应，常见问题是愿景很丰满、边界和取舍却缺失。

**Why it happens:**
文档生成比状态编排更容易做 demo。很多系统先把聊天做好，最后接一个“生成 PRD”按钮，实际上并没有定义 PRD 的数据契约。

**How to avoid:**
- 先定义 PRD schema，再定义每个字段如何从断言层映射出来。
- 关键章节必须带验证规则：问题陈述要有目标用户与痛点证据，方案要有边界，范围要有非目标。
- PRD 生成拆成“字段映射 -> 缺口检查 -> 文案编排 -> 用户确认”四步。
- 对存在冲突的章节禁止静默出文，先回到澄清流程。

**Warning signs:**
- PRD 中“解决方案”写得很多，但“为什么做 / 不做什么”写得很弱。
- 对话里讨论过的矛盾点在 PRD 中消失。
- 同一会话重复导出，文档结构和结论波动很大。

**Phase to address:**
Phase 4「PRD schema 与生成编排」

---

### Pitfall 8: 缺乏“适当依赖”设计，用户会把 AI 草稿当判断本身

**What goes wrong:**
独立开发者时间紧、产品经验不稳定，最容易把 AI 给出的措辞、优先级和结论直接当成正确答案。这样会把“辅助澄清”滑向“替代判断”。

**Why it happens:**
研究表明，人会对 AI 建议产生 overreliance，尤其当验证成本高、解释难懂或系统语言过度自信时。生成式产品若不给验证摩擦和可检验依据，会放大这种偏差。

**How to avoid:**
- 对高影响建议提供“为什么这样判断”“还有什么替代解释”“你要确认什么”三件套，而不是只给建议。
- 在关键节点加入轻量 friction，例如要求用户确认“这是事实/偏好/假设”。
- 避免用过度确定语气包装推断结论。
- 把“用户修正 AI 的频率”和“用户拒绝建议后的完成率”纳入质量指标。

**Warning signs:**
- 用户很少修改 AI 草稿，却频繁在后续会话里推翻整份方向。
- 系统解释主要是修辞性解释，不是可检验依据。
- 用户反馈集中在“看起来都对，但不知道是不是我真的要的”。

**Phase to address:**
Phase 5「人机协作校准与验证体验」

---

### Pitfall 9: 忽视长期多轮会话中的上下文漂移与记忆衰减

**What goes wrong:**
随着工作台会话变长，系统逐渐遗忘早期约束、过度依赖最近几轮输入，或者把旧上下文压缩得过度抽象，导致后面判断失真。

**Why it happens:**
多轮对话本身就是当前 LLM 的薄弱点。研究显示，多轮设置下总体性能显著下降，原因不只是能力下降，还包括 unreliability 上升、早期假设锁死、上下文忽视和记忆衰减。

**How to avoid:**
- 不要把“完整聊天历史 + 一个 summary”当唯一记忆机制；应维护结构化长期记忆与当前焦点上下文。
- 关键断言始终从状态层检索，不依赖模型自行回忆。
- 定期执行一致性审计：检查当前回合回答是否违反已确认约束。
- 会话过长时，显式创建阶段快照，并允许从快照重开分支。

**Warning signs:**
- 越聊越容易忘记之前明确说过的非目标、约束或用户类型。
- 近期输入轻易覆盖早期高置信结论。
- 长会话的 PRD 质量明显差于短会话。

**Phase to address:**
Phase 1「长期记忆与状态层」+ Phase 5「长会话回归评测」

---

### Pitfall 10: 用通用聊天指标评估产品，导致真正的需求澄清能力被掩盖

**What goes wrong:**
团队用回复满意度、对话时长、生成字数、导出率来判断产品效果，却没有衡量“澄清是否真的减少歧义、暴露矛盾、形成可执行 PRD”。结果会把一个“很会聊”的系统误判成“很会收敛”的系统。

**Why it happens:**
通用聊天指标容易拿到，也容易看起来增长。但这个领域的成败关键是 requirements quality，不是 conversational smoothness。

**How to avoid:**
- 建立领域指标：矛盾检出率、缺口暴露率、确认覆盖率、PRD 字段可追溯率、用户后续重写率。
- 设计回归用例：同一模糊想法在不同轮次后，系统是否能稳定收敛到明确问题、方案、边界。
- 把“用户修改 AI 草稿的质量提升”纳入评估，而不是只看是否接受。
- 对关键阶段做人工标注评测，而不是完全依赖 thumbs up/down。

**Warning signs:**
- 满意度不错，但导出的 PRD 经常需要大改。
- 系统回复越来越长，需求反而越来越模糊。
- 团队很难回答“系统到底在哪些类型的矛盾上有效”。

**Phase to address:**
Phase 5「评估体系与观测面板」

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| 只维护单段 summary，不建结构化断言层 | 开发快、接入成本低 | 无法稳定做矛盾检测、追溯、回滚 | 仅原型验证，不能进入正式 roadmap 主线 |
| PRD 最后一次性生成 | demo 效果直观 | 文档与对话脱节，无法验证字段来源 | 仅用于手工内部演示 |
| 全靠 LLM 做矛盾检测 | 实现简单 | 召回和可解释性不稳定，难做回归 | 低风险提示可接受，高价值约束不应如此 |
| 选项式引导只做按钮，不留自由输入 | 降低交互复杂度 | 用户被默认答案绑架，产品同质化 | 永远不应作为关键字段唯一入口 |
| 用“导出率”代表收敛质量 | 数据好看 | 误导团队优化方向 | 永远不应单独使用 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LLM 对话服务 | 直接把完整聊天历史塞进模型，指望模型自己维护状态 | 使用结构化状态层、阶段快照和按需检索上下文 |
| 摘要/快照系统 | 摘要与 PRD、矛盾检测各自维护独立文本版本 | 统一基于同一套断言和证据模型 |
| 导出能力 | 导出时重新让模型“理解一遍”会话 | 导出只负责编排已验证状态，不重新发明事实 |
| 反馈采集 | 只收 thumbs up/down，没有定位到具体断言或阶段 | 反馈要绑定到具体建议、具体追问、具体 PRD 字段 |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 长会话全量重总结 | 每轮延迟升高，摘要越来越漂 | 增量更新断言层，只重算受影响字段 | 通常在 20+ 轮后明显恶化 |
| 每次回复都跑全量矛盾检测 | 响应慢、成本高 | 只对新增或受影响断言做局部检测 | 中高活跃用户下很快不可承受 |
| 单一超长 prompt 承担全部职责 | 输出不稳定、难调试 | 拆分为澄清、检测、编排、导出等阶段任务 | 一旦需求复杂或会话分叉就容易失控 |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| 把用户创业想法、未公开需求直接长期喂给外部模型且无最小化策略 | 敏感商业信息泄露、信任受损 | 做数据分级、最小必要传输、模型/日志保留策略透明化 |
| 在导出或分享时暴露内部推断与未确认假设，但没有标识 | 用户把假设当事实传播 | 导出时明确区分已确认/推断/未决 |
| 把历史会话或相似项目直接作为 few-shot 上下文，却没有租户隔离 | 跨用户信息泄露 | 多租户隔离、检索过滤、审计日志 |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| 追问像审讯，不像协作 | 用户疲劳、放弃回答 | 用阶段性总结和可反应选项降低负担 |
| 矛盾提示只有“红字提醒”没有下一步 | 用户知道有问题但不知道怎么改 | 每个矛盾都附带建议澄清问题和影响章节 |
| PRD 看起来很完整，但不显示不确定性 | 用户误判成熟度 | 显式展示未决项、假设和确认度 |
| AI 语气过度自信 | 放大用户误信 | 在推断场景下降低确定性表达，并给出依据 |

## "Looks Done But Isn't" Checklist

- [ ] **矛盾检测：** 常缺少跨轮次检测与来源定位，验证是否能指出冲突双方及 turn id。
- [ ] **PRD 导出：** 常缺少未决问题与假设标记，验证导出文档是否区分 confirmed / inferred / missing。
- [ ] **收敛控制：** 常只有“继续问”没有“阶段收束”，验证是否存在明确停问条件与 checkpoint。
- [ ] **选项式引导：** 常缺少自由补充入口，验证关键字段是否允许用户改写而非只能点选。
- [ ] **会话记忆：** 常缺少早期约束保护，验证长会话回归下是否仍保留非目标和核心边界。

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| 过早写死需求 | HIGH | 回滚到断言层，清除未确认结论，重开澄清分支，并重新生成受影响 PRD 章节 |
| 矛盾未被识别 | MEDIUM | 补跑结构化冲突扫描，人工确认冲突类型，再触发定向追问 |
| 过度追问不收敛 | LOW | 立即生成阶段总结，切换到选项式收束，并限制下一轮问题数 |
| 默认选项绑架用户 | MEDIUM | 对关键字段追加“反例/自定义”轮次，并回收默认接受样本做评测 |
| 长会话漂移 | MEDIUM | 基于最近可靠快照重建焦点上下文，避免继续沿错误摘要累积 |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 过早写死需求 | Phase 1 + Phase 2 | 未确认内容不会直接进入 PRD 主体；澄清触发率符合预期 |
| 矛盾检测只是摘要 | Phase 3 | 冲突输出可定位两端证据、类型与下一步问题 |
| 只会追问不会收敛 | Phase 2 + Phase 4 | 存在明确 checkpoint 与停问条件；中间产物稳定生成 |
| 选项式引导绑架用户 | Phase 2 + Phase 5 | 关键字段的自定义率、修正率与后续满意度可观测 |
| 未知项被静默补全 | Phase 1 + Phase 4 | 导出文档保留 missing / inferred 标记，不被润色抹平 |
| 无来源追溯 | Phase 1 | 任一 PRD 断言可回溯到来源轮次与确认状态 |
| PRD 只是大作文 | Phase 4 | 各章节由 schema 驱动生成，缺字段时触发缺口而非编造 |
| 用户过度依赖 AI | Phase 5 | 高风险建议存在验证摩擦；用户能识别事实/假设/偏好 |
| 长会话漂移 | Phase 1 + Phase 5 | 长会话回归集下约束保留率稳定 |
| 指标错位 | Phase 5 | 仪表盘包含澄清质量和 requirements quality，而非只看聊天指标 |

## Sources

- ICLR 2025, *Modeling Future Conversation Turns to Teach LLMs to Ask Clarifying Questions*  
  https://proceedings.iclr.cc/paper_files/paper/2025/file/97e2df4bb8b2f1913657344a693166a2-Paper-Conference.pdf
- arXiv, 2025-05-09, *LLMs Get Lost In Multi-Turn Conversation*  
  https://arxiv.org/abs/2505.06120
- arXiv, 2025-03-23, *An Empirical Study of the Role of Incompleteness and Ambiguity in Interactions with Large Language Models*  
  https://arxiv.org/abs/2503.17936
- Springer, 2024, *Automated requirement contradiction detection through formal logic and LLMs*  
  https://link.springer.com/article/10.1007/s10515-024-00452-x
- arXiv / ICSE NIER 2025, *On the Impact of Requirements Smells in Prompts: The Case of Automated Traceability*  
  https://arxiv.org/abs/2501.04810
- ICSME 2025 Industry Track, *Requirements Ambiguity Detection and Explanation with LLMs: An Industrial Study*  
  https://conf.researchr.org/details/icsme-2025/icsme-2025-industry-track/8/Requirements-Ambiguity-Detection-and-Explanation-with-LLMs-An-Industrial-Study
- RE 2025 Doctoral Symposium, *Building Software Functional Requirements Lists Using RAG with Distinct LLMs in Multiple Interactions*  
  https://conf.researchr.org/details/RE-2025/RE-2025-doctoral-symposium/4/Building-Software-Functional-Requirements-Lists-Using-RAG-with-Distinct-LLMs-in-Multi
- Intercom Help, *Copilot tips and best practices*  
  https://www.intercom.com/help/en/articles/9121380-copilot-tips-and-best-practices
- Intercom, 2024-09-16, *Manage knowledge audiences and targeting for Fin AI Copilot*  
  https://www.intercom.com/changes/en/69913-manage-knowledge-audiences-and-targeting-for-fin-ai-copilot
- Microsoft Research, 2025, *Fostering appropriate reliance on GenAI*  
  https://www.microsoft.com/en-us/research/wp-content/uploads/2025/03/Appropriate-Reliance-Lessons-Learned-Published-2025-3-3.pdf
- Stanford / CSCW 2023, *Explanations can reduce overreliance on AI systems during decision-making*  
  https://arxiv.org/abs/2212.06823

---
*Pitfalls research for: AI brainstorming / PRD-copilot products for indie developers*
