# Web 端 Tailwind CSS 与 shadcn/ui 基础接入设计

## 背景

当前 `apps/web` 已经在 JSX 中大量使用 `min-h-screen`、`bg-stone-100`、`text-neutral-950` 这类 Tailwind 类名，但项目尚未安装和配置 Tailwind CSS，因此这些样式类目前不会生效。

同时，项目还没有统一的 UI 组件基础层，后续如果继续直接手写业务组件，样式复用、交互一致性和扩展成本都会变差。

## 目标

本次只完成 Web 端的基础设施接入，不做大范围页面重构：

1. 让现有页面上的 Tailwind 类名真实生效。
2. 接入 shadcn/ui 所需的最小基础设施。
3. 提供后续可复用的公共工具和基础组件。
4. 以最小改动验证接入成功，避免一次性改动现有业务页面。

## 非目标

本次不包含以下内容：

1. 不批量替换现有业务组件。
2. 不做新的视觉改版。
3. 不一次性引入大量 shadcn/ui 组件。
4. 不处理与本次接入无关的测试环境问题。

## 方案选择

### 方案 A：最小基础接入

内容：

1. 安装 `tailwindcss`、`postcss`、`autoprefixer`。
2. 配置 Tailwind 扫描路径与全局样式入口。
3. 安装 shadcn/ui 的基础依赖，例如 `class-variance-authority`、`clsx`、`tailwind-merge`、`lucide-react`。
4. 补齐 `components.json`、`cn` 工具函数和少量基础组件。
5. 选择一个小页面或局部组件验证接入结果。

优点：

1. 改动范围小，风险低。
2. 能快速纠正“写了 Tailwind 类但没生效”的当前问题。
3. 为后续逐步组件化提供稳定底座。

缺点：

1. 短期内 UI 提升有限。
2. 现有业务组件仍然保留较多手写结构。

### 方案 B：基础接入 + 批量页面改造

优点是视觉收益更快，缺点是改动面大、回归点多，不适合当前阶段。

结论：采用方案 A。

## 设计

### 1. 样式基础设施

在 `apps/web` 中新增：

1. `tailwind.config.ts`
2. `postcss.config.js`
3. `src/app/globals.css`

其中：

1. `tailwind.config.ts` 负责声明内容扫描范围，覆盖 `src/app`、`src/components`、`src/lib`。
2. `globals.css` 负责引入 Tailwind 的基础层、组件层和工具层。
3. `src/app/layout.tsx` 负责导入 `globals.css`。

### 2. shadcn/ui 基础层

新增以下基础资产：

1. `components.json`
2. `src/lib/utils.ts`
3. `src/components/ui/button.tsx`
4. `src/components/ui/input.tsx`
5. `src/components/ui/card.tsx`

说明：

1. `utils.ts` 提供 `cn` 合并函数。
2. 基础组件先控制在最小集合，只满足后续页面复用的起点，不扩散范围。

### 3. 验证方式

采用“基础接入 + 局部验证”的方式：

1. 保持现有页面结构不大改。
2. 选取登录页或工作台入口页做最小替换，确认：
   - Tailwind 类已生效
   - 基础 UI 组件可正常渲染
   - 不影响现有页面路径和业务流程

## 数据流与运行影响

本次改动只涉及前端样式与组件层：

1. 不改变 API 请求。
2. 不改变路由结构。
3. 不改变状态管理逻辑。
4. 不涉及数据库和后端。

## 风险与处理

### 1. Tailwind 版本与 Next 15 兼容性

处理方式：

1. 采用与当前 Next 生态兼容的稳定版本组合。
2. 接入后优先跑一次构建或类型检查确认。

### 2. 测试环境与样式工具链冲突

当前仓库已有 Vitest 启动异常，属于独立问题。

处理方式：

1. 本次先做样式接入验证。
2. 若测试仍因既有依赖问题失败，需要单独处理测试环境。

### 3. 现有类名与设计 token 不统一

处理方式：

1. 本次不重构视觉规范。
2. 先保证现有 Tailwind 类可以运行。
3. 后续再逐步引入统一设计 token。

## 验收标准

满足以下条件即视为完成：

1. `apps/web` 已安装并配置 Tailwind CSS。
2. `src/app/layout.tsx` 已加载全局样式。
3. 项目中现有 Tailwind 类名能在页面上生效。
4. shadcn/ui 基础依赖和最小组件已接入。
5. 至少一个页面或局部组件已使用基础 UI 组件完成验证。

