# PRD Structured Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `apps/api` 增加“规则兜底 + 模型结构化提取”的混合式 PRD 状态抽取能力，并保持重生成不推进 state / PRD。

**Architecture:** 在现有消息链路中新增结构化提取层。规则提取负责稳定兜底，模型提取负责提升语义质量，服务端统一做校验、归一化和降级，再把结果接入现有 `state_patch` / `prd_patch` / `prd.updated` 持久化链路。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, httpx, pytest

---

### Task 1: 定义结构化提取契约

**Files:**
- Create: `apps/api/app/agent/extractor.py`
- Modify: `apps/api/app/agent/runtime.py`
- Test: `apps/api/tests/test_agent_runtime.py`

- [ ] **Step 1: 写运行时失败测试**
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 定义 `StructuredExtractionResult` 和规则提取逻辑**
- [ ] **Step 4: 让 `run_agent` 支持模型结果优先、规则兜底**
- [ ] **Step 5: 运行运行时测试确认通过**

### Task 2: 增加模型结构化提取调用

**Files:**
- Modify: `apps/api/app/services/model_gateway.py`
- Test: `apps/api/tests/test_model_gateway.py`

- [ ] **Step 1: 写模型提取失败测试和成功测试**
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 实现结构化提取调用与 JSON 解析**
- [ ] **Step 4: 运行模型网关测试确认通过**

### Task 3: 接入消息服务并实现降级

**Files:**
- Modify: `apps/api/app/services/messages.py`
- Test: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_messages_stream.py`
- Test: `apps/api/tests/test_sessions.py`

- [ ] **Step 1: 写消息服务失败测试，覆盖模型结果优先和失败回退**
- [ ] **Step 2: 运行测试确认失败**
- [ ] **Step 3: 在新消息链路中接入结构化提取**
- [ ] **Step 4: 保持重生成只改 version，不推进 state / PRD**
- [ ] **Step 5: 运行消息、会话测试确认通过**

### Task 4: 做全量回归验证

**Files:**
- Test: `apps/api/tests`

- [ ] **Step 1: 运行 `./.venv/bin/python -m pytest tests -q`**
- [ ] **Step 2: 检查无失败、无新增回归**

