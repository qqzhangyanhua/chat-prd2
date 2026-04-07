# PRD 结构化提取补全设计

## 1. 背景

当前 `apps/api` 已经具备会话、消息流、状态快照、PRD 快照、Markdown 导出的基础设施，但 PRD 智能体的状态推进仍然是占位实现：

- 新消息虽然会生成新的 `state_version` 和 `prd_snapshot`
- 但 `state_patch` / `prd_patch` 主要依赖简单轮次推进
- 重生成已经被修正为不推进 `state` / `PRD`

这意味着系统已经有“可持久化的骨架”，但还没有“可信的结构化提取器”。

本次补全目标不是直接做一个完全自由的 agent，而是在现有架构中加入一个可控、可测试、可降级的结构化提取层。

## 2. 目标

本次设计只解决一个问题：

把用户自然语言输入稳定地提取成可落库的 `state_patch` 和 `prd_patch`，并让这些结果驱动右侧 PRD 面板与 Markdown 导出。

本次范围内必须达成：

- 新消息链路支持结构化提取
- 提取结果只允许更新 `target_user`、`problem`、`solution`、`mvp_scope`
- 当模型提取不可靠时，可以自动降级到规则结果
- 重生成继续只影响 assistant version，不影响 `state` / `PRD`

本次范围外不做：

- `goal`、`risks`、`options`、`success_metrics` 等扩展字段提取
- 多轮复杂推理记忆
- 让模型直接生成完整 PRD 文档
- 前端协议大改

## 3. 方案对比

### 方案 A：继续增强纯规则提取

优点：

- 最稳定
- 最容易测试
- 无额外模型调用成本

缺点：

- 对自然语言表达变化敏感
- 很快会演变成一堆脆弱规则
- 无法有效理解复杂用户描述

### 方案 B：规则兜底 + 模型结构化提取

优点：

- 提取质量明显高于纯规则
- 规则可以兜住空话、短句、格式化列表等低层问题
- 可以对模型输出做强校验，降低污染主状态的风险

缺点：

- 比纯规则多一次调用
- 需要设计提取协议和降级逻辑

### 方案 C：完全交给模型返回结构化 patch

优点：

- 语义能力上限最高
- 规则代码最少

缺点：

- 最难调试
- 模型一旦返回脏结构会直接污染主状态
- 稳定性和可控性最差

### 推荐

采用方案 B。

原因：

- 当前代码库已经有 `state_patch` / `prd_patch` / `prd.updated` 的消费链路，适合引入结构化提取结果
- 当前阶段最重要的是“可信地沉淀 PRD”，不是追求最智能
- 混合方案能以较低风险提升语义提取质量

## 4. 总体架构

在现有链路中新增一个“结构化提取层”：

```text
用户输入
  -> 规则预处理
  -> 模型结构化提取
  -> 服务端校验 / 归一化 / 降级
  -> Agent Runtime 决定下一步 action
  -> Messages Service 持久化 state / PRD
  -> SSE prd.updated
```

职责划分：

- `agent/extractor.py`
  负责规则预处理、模型提取、结果合并
- `agent/runtime.py`
  负责“基于新状态决定下一步动作”
- `services/model_gateway.py`
  负责新增结构化提取调用，不与聊天生成混用
- `services/messages.py`
  负责把提取结果接入新消息持久化链路

## 5. 数据契约

新增结构化提取结果对象：

```python
StructuredExtractionResult
- should_update: bool
- state_patch: dict
- prd_patch: dict
- confidence: str
- reasoning_summary: str
```

允许的 `state_patch` 字段仅限：

- `target_user: str`
- `problem: str`
- `solution: str`
- `mvp_scope: list[str]`
- `stage_hint: str`
- `iteration: int`

允许的 `prd_patch` 字段仅限：

- `target_user`
- `problem`
- `solution`
- `mvp_scope`

每个 PRD section 结构固定为：

```python
{
  "title": str,
  "content": str,
  "status": "confirmed" | "inferred",
}
```

### 关键约束

- 任何非白名单字段一律丢弃
- `mvp_scope` 在状态里必须是 `list[str]`
- `mvp_scope` 在 PRD 里统一格式化成单个字符串内容
- 空字符串、空列表、全空白内容视为无效更新
- `iteration` 不允许由模型自由指定，只能由服务端控制

## 6. 规则预处理

规则层不负责完整理解语义，只负责三件事：

1. 规范化输入
   - 去除多余空白
   - 过滤“继续”“好的”“嗯”这类推进词

2. 低成本识别明显结构
   - 使用换行、顿号、逗号、分号拆分 MVP 列表候选
   - 对极短文本直接作为单字段候选

3. 产出规则 patch 候选
   - 如果当前缺口是 `target_user`，则将有效输入直接作为 `target_user` 候选
   - 如果当前缺口是 `problem`，则将有效输入直接作为 `problem` 候选
   - 其他字段同理

规则结果的定位是“兜底”，不是最终权威来源。

## 7. 模型结构化提取

新增一个专用调用，不复用聊天回复生成。

模型输入包含：

- 当前结构化 state
- 当前缺口字段
- 用户原始输入
- 严格的 JSON 输出要求

模型输出目标：

- 是否建议更新
- 建议更新哪个字段
- 建议写入的结构化内容
- 简短原因摘要
- 置信度

### 输出校验

服务端在接受模型结果前，必须进行：

- JSON 解析校验
- 字段白名单校验
- 类型校验
- 空值校验
- section 标题与状态归一化

不合法则直接丢弃模型结果并降级。

## 8. 合并与降级策略

合并顺序：

1. 先生成规则结果 `rule_result`
2. 再生成模型结果 `llm_result`
3. 若 `llm_result` 合法且 `confidence != low`，优先使用模型结果
4. 若 `llm_result` 不合法、为空或低置信，回退规则结果
5. 若两者都无有效结果，`should_update = false`

这样做的目的：

- 尽量使用模型的语义能力
- 避免模型返回脏 patch 时污染主状态
- 确保最差情况下系统仍可推进

## 9. 新消息与重生成语义

### 新消息

新消息链路保持现在的主语义：

- 调结构化提取
- 生成新的 `state_patch` / `prd_patch`
- 生成新的 `state_version` / `prd_snapshot`
- 发出 `prd.updated`

### 重生成

重生成不变：

- 不重新做结构化提取
- 不推进 `state_version`
- 不推进 `prd_snapshot`
- 不发 `prd.updated`
- 只新增 assistant version 并覆盖 latest assistant 镜像 message

## 10. 测试策略

### 10.1 运行时测试

新增覆盖：

- 模型结果合法时优先使用模型 patch
- 模型结果非法时回退规则 patch
- 模型结果低置信时回退规则 patch
- 纯推进词输入时 `should_update = false`

### 10.2 消息服务测试

新增覆盖：

- 新消息成功时 state / PRD 使用结构化提取结果
- 模型提取异常时仍可使用规则 patch
- `prd.updated` 使用最终合并后的 section 数据

### 10.3 会话 / 导出测试

新增覆盖：

- `GET /api/sessions/{id}` 返回更新后的 snapshot
- 导出 Markdown 包含结构化提取后的真实 section 内容

## 11. 风险与边界

### 风险 1：模型输出不稳定

控制方式：

- 强 schema 校验
- 低置信降级
- 规则兜底

### 风险 2：模型与规则冲突

控制方式：

- 只接受单轮最小 patch
- 只允许白名单字段
- 当前缺口优先原则不变

### 风险 3：把错误信息写入主状态

控制方式：

- 对超短文本、空话、推进词不更新
- 对 `mvp_scope` 做列表归一化和去重
- 对不合法 patch 直接丢弃

## 12. 结论

本次推荐以“规则兜底 + 模型结构化提取”的混合方案补全 PRD 智能体。

这样可以在不推翻现有会话、流式事件、快照、导出链路的前提下，把当前“占位式状态推进”升级成“可控的结构化语义提取”。

这是比继续堆规则更可靠、比完全依赖模型更稳妥的中间路线。
