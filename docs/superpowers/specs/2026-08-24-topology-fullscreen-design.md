# 拓扑图全屏与体验优化设计

日期：2026-08-24
状态：已确认（用户批准）

## 背景与目标

拓扑图（`frontend/src/components/TopologyView.vue`）当前存在四个问题：

1. 浏览器全屏（F11）时页头 + tab 栏两级菜单仍然占位，全屏效果差
2. 悬停/轮询会触发 `fg.graphData()` 重置，图反复重新布局、节点跳动
3. 节点圆点太小（最小 4px），无法辨识设备类型
4. 标签字号默认 9，用户希望默认最小

用户选择：页面内全屏按钮（Fullscreen API）+ 大圆点内绘制类型图标。

## 方案

### 1. 全屏模式

- 工具栏新增「全屏」按钮，点击对 `.topology-wrap` 容器调用 `requestFullscreen()`
- 全屏态左上角悬浮「← 返回主页」链接：退出全屏并切换到「设备」标签页
- Esc 退出为浏览器原生行为
- 全屏铺满由 CSS `:fullscreen` 选择器实现；画布尺寸同步复用现有 ResizeObserver（0.4.11 引入）

组件间通信：TopologyView 不持有 tab 状态，「返回主页」通过 emit `back-home` 事件，
MainView 监听后将 `activeTab` 置为 `'devices'`。

### 2. 停止重新布局，支持拖拽摆位

- 删除 `onNodeHover` 回调中的 `fg.graphData(graphData.value)` 重置调用；
  悬停高亮依赖 force-graph 连续渲染（rAF），仅需更新 `hoverNodeId`
- 新增 `syncGraphData()`：按节点 id 复用旧节点对象，原地更新 name/type/status/
  latency_ms/val 等字段，保留 x/y/vx/vy；删除消失的节点、追加新增的节点；
  链接按 (source, target) 去重后重建。每当 `graphData` computed 变化时调用
  （替代现有仅监听 nodes.length 的 watch）
- 拖拽为 force-graph 内置能力（`enableNodeDrag` 默认开启），松手后坐标保留，
  后续轮询不再重置

### 3. 节点样式：大圆点 + 类型图标

- 半径基准从 4px 提升到 8px，分组节点按子节点数适度增大（沿用 val 平方根缩放）
- 圆点内居中绘制类型 emoji（白色发光背景不变，状态色/离线闪烁逻辑保持）：

  | 类型 | 图标 |
  |------|------|
  | group | 📁 |
  | server | 🖥️ |
  | switch | 🔀 |
  | terminal | 💻 |
  | camera | 📷 |
  | nvr | 🎛️ |
  | router | 📡 |
  | firewall | 🛡️ |
  | ap | 📶 |
  | printer | 🖨️ |
  | nas | 💾 |
  | ups | 🔋 |
  | unmanaged_switch | 🔌 |

- 自定义类型回退显示类型名首字（`typeLabel(type)[0]`），未知类型显示 `?`
- 图标映射抽为纯函数 `typeGlyph(type)` 并导出，便于单测

### 4. 字号默认最小

- `labelFontSize` 初始值 9 → 6（滑块 min 不变）

## 测试

TopologyView.spec.js 新增用例：

- 默认字号为 6
- 悬停节点不调用 `fg.graphData()` 重置
- 数据刷新（graphData 变化）时旧节点对象被复用（x/y 保留）
- `typeGlyph` 映射：内置类型返回对应 emoji、自定义类型返回首字、未知返回 `?`
- 点击全屏按钮调用容器 `requestFullscreen()`

回归：现有 TopologyView 用例 + 全量前端测试 + 构建。

## 不做的事（YAGNI）

- 不做独立 /topology 路由
- 不做节点位置服务端持久化（仅内存中保留本次会话位置）
- 不改 Element Plus 图标体系（DeviceTree/Table 处不动）
