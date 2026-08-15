# 拓扑图节点标签控制设计

日期：2026-08-15
状态：已确认

## 背景

拓扑图节点标签目前硬编码为 `12px sans-serif` 且始终显示（`TopologyView.vue` 的 `drawNode` 内第 76 行）。用户反馈字号偏大，希望：字号可调、标签可隐藏。

## 需求

在拓扑图页顶部提供小型工具栏，支持：

1. **字号调整**：滑块实时改变节点标签字号，范围 6–18px，步进 1px，默认 9px。
2. **标签显示/隐藏**：开关控制标签显示。隐藏时悬停节点临时显示该节点标签，移开后再隐藏。

## 设计

采用方案 A（响应式 `ref` + force-graph 动画循环自动重绘），不重建图、不重置力导向布局。

### 状态

新增两个响应式状态（`TopologyView.vue` `<script setup>`）：

```js
const labelFontSize = ref(9)   // 默认 9px
const showLabels = ref(true)   // 默认显示
```

### 绘制逻辑（`drawNode`）

- 字号：`ctx.font = `${labelFontSize.value}px sans-serif``（替代硬编码 `12px`）。
- 隐藏逻辑：当 `showLabels` 为 `false` 且当前节点不是悬停节点（`node.id !== hoverNodeId.value`）时，跳过标签文字绘制；悬停节点仍绘制标签。`hoverNodeId` 已存在于现有代码。

```js
if (showLabels.value || node.id === hoverNodeId.value) {
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.font = `${labelFontSize.value}px sans-serif`
  ctx.textAlign = 'center'
  ctx.fillText(node.name, node.x, node.y - r - 4)
}
```

### 工具栏（模板）

在 `.topology-wrap` 顶部、`.graph` 之前添加工具栏：

```
字号：滑块（min=6 max=18 step=1，v-model=labelFontSize，实时）
显示标签：开关（v-model=showLabels）
```

- 滑块用 `el-slider`（实时生效：`drawNode` 在每次动画帧重绘时读取最新 `labelFontSize`，无需额外触发）。
- 开关用 `el-switch` 或 `el-checkbox`，文案"显示标签"。

### 布局

`.topology-wrap` 变为纵向 flex：工具栏在上，`.graph` 占据剩余空间。调整现有样式（`.topology-wrap` 加 `display:flex; flex-direction:column`；`.graph` 加 `flex:1`）。

## 测试

更新 `frontend/src/components/__tests__/TopologyView.spec.js`：

1. 渲染后工具栏存在（字号滑块、显示标签开关）。
2. 改变 `labelFontSize` 后，`drawNode` 以新字号绘制（通过 `fgMock.nodeCanvasObject` 捕获回调，调用之并验证 `ctx.font`）。
3. `showLabels=false` 时，非悬停节点不绘制标签；悬停节点仍绘制。
4. 现有测试保持通过。

## 范围

- 仅前端 `TopologyView.vue` 及其测试。
- 不改后端、不改设置持久化（工具栏状态为会话内内存，刷新重置为默认值 9px/显示）。