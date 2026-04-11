# Workspace 显式入口设计

**目标**

修复工作区中显式入口被自动重定向到最近活跃会话的问题，保证用户点击“新建会话”或 “Home” 时都能稳定进入对应的空白入口页。

**现状问题**

当前 `/workspace` 入口页会在加载后调用 `listSessions`，只要存在历史会话就自动跳转到最近活跃的 `sessionId`。这会吞掉用户的显式意图：点击“新建会话”时会被带回旧会话，点击 “Home” 时也无法稳定停留在工作区入口页。

**方案对比**

1. 直接取消 `/workspace` 的自动跳转
优点是实现简单；缺点是会改变“进入工作区自动续上最近会话”的现有行为。

2. 新增显式入口路由
优点是职责清晰，兼容现有 `/workspace` 自动跳转行为，同时确保“新建会话”进入 `/workspace/new`、Home 进入 `/workspace/home`；缺点是需要增加两个新路由。

3. 使用 `/workspace?mode=new` 关闭自动跳转
优点是无需新增目录；缺点是 URL 语义弱，后续调用点容易漏传参数。

**推荐方案**

采用方案 2。

**设计**

- 保留 `/workspace` 作为“工作区默认入口”，继续支持自动恢复最近会话。
- 新增 `/workspace/new` 和 `/workspace/home` 页面，统一复用 `WorkspaceEntry` 组件。
- 为 `WorkspaceEntry` 增加 `autoRedirectToLatest` 开关，默认 `true`。
- 当 `autoRedirectToLatest` 为 `false` 时，不执行最近会话自动跳转，直接展示创建表单。
- 将显式入口统一改为清晰路由：Home 跳转 `/workspace/home`，New Session 跳转 `/workspace/new`。

**测试策略**

- 为 `WorkspaceEntry` 增加测试，验证 `autoRedirectToLatest={false}` 时即使存在历史会话也不会自动跳转。
- 为 `SessionSidebar` 增加测试，验证“新建会话”按钮跳转到 `/workspace/new`。
- 为新增 `/workspace/new` 与 `/workspace/home` 页面增加测试，验证在存在历史会话时仍展示创建界面。
