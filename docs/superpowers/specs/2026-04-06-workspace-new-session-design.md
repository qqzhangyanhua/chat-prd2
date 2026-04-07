# Workspace 新建会话入口设计

**目标**

修复工作区中“新建会话”被自动重定向到最近活跃会话的问题，保证用户可以稳定进入空白的新建会话页。

**现状问题**

当前 `/workspace` 入口页会在加载后调用 `listSessions`，只要存在历史会话就自动跳转到最近活跃的 `sessionId`。这导致从会话侧边栏点击“新建会话”后，用户实际上会再次进入旧会话，而不是空白创建页。

**方案对比**

1. 直接取消 `/workspace` 的自动跳转
优点是实现简单；缺点是会改变“进入工作区自动续上最近会话”的现有行为。

2. 新增 `/workspace/new` 作为显式新建入口
优点是职责清晰，兼容现有 `/workspace` 自动跳转行为，同时确保“新建会话”永远进入空白页；缺点是需要增加一个新路由。

3. 使用 `/workspace?mode=new` 关闭自动跳转
优点是无需新增目录；缺点是 URL 语义弱，后续调用点容易漏传参数。

**推荐方案**

采用方案 2。

**设计**

- 保留 `/workspace` 作为“工作区入口”，继续支持自动恢复最近会话。
- 新增 `/workspace/new` 页面，复用 `WorkspaceEntry` 组件。
- 为 `WorkspaceEntry` 增加 `autoRedirectToLatest` 开关，默认 `true`。
- 当 `autoRedirectToLatest` 为 `false` 时，不执行最近会话自动跳转，直接展示创建表单。
- 将 `WorkspaceEntry` 内部的 “New Session” 按钮和 `SessionSidebar` 的“新建会话”按钮统一改为跳转 `/workspace/new`。

**测试策略**

- 为 `WorkspaceEntry` 增加测试，验证 `autoRedirectToLatest={false}` 时即使存在历史会话也不会自动跳转。
- 为 `SessionSidebar` 增加测试，验证“新建会话”按钮跳转到 `/workspace/new`。
- 为新增 `/workspace/new` 页面增加测试，验证在存在历史会话时仍展示创建界面。
