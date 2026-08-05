# WebWeaver Phase 1 增强：前端自动刷新 + 节点移动

## 背景

用户手工测试 Phase 1 时发现两个体验问题：

1. **新节点"不被巡检"的感受**：后端 APScheduler 每 5 分钟会巡检所有有 IP 的节点（含后添加的），但前端 v1 无轮询/WebSocket，界面停留在旧状态，必须手动点「刷新」或「立即巡检」才能看到新状态。
2. **节点无法移动到不同上下级**：后端 `update_device` 已支持修改 `parent_id`（含自引用与环检测），但前端编辑弹窗没有父级选择器。

## 范围

仅修改 `frontend/`，后端无需改动。

## 需求 1：前端自动刷新

- `MainView.vue` 组件挂载后启动 `setInterval(() => store.load(), 30000)`，组件卸载时 `clearInterval` 清理。
- 复用现有 `devices` store 的 `load()`（GET `/api/devices/tree`）。
- 刷新应静默进行：不阻塞用户操作，不因刷新中断正在进行的右键菜单/弹窗交互。
- 用户手动「刷新」按钮逻辑不变。

## 需求 2：编辑弹窗选父级（移动节点）

- `DeviceTree.vue` 编辑弹窗新增「上级分组」下拉选择器（`el-tree-select` 或 `el-select`）。
- 数据源为可作为父级的节点列表，需**排除自身及其所有后代**（防止环），允许清空表示移到根级（`parent_id = null`）。
- 保存时把选中的父级 id 放入 `parent_id` 提交。
- 后端已有防线：`update_device` 抛 `parent cannot be self`（自引用）、`cycle not allowed`（成环）、`device name already exists under this parent`（同父重名 → 409）。前端过滤为第一道防护。

## 错误处理

- 保存失败（如同父重名 409）沿用上一轮已加的错误提示（`ElMessage.error(error.response?.data?.detail)`），弹窗保持打开供修改。

## 测试

- **MainView**：组件测试验证轮询启动与卸载清理（`vi.useFakeTimers`）。
- **DeviceTree**：组件测试验证父级选择器渲染、候选节点排除自身及后代、提交载荷包含正确的 `parent_id`。
- 回归：现有前端 5 个用例 + `npm run build`；后端 38 个用例不受影响。
