# 设计：拓扑关系图谱（Obsidian Graph View 风格）

日期：2026-08-14
状态：已批准

## 背景与目标

为 WebWeaver 新增"拓扑图"独立 tab，用 `2d-force-graph` 将设备树渲染为暗黑霓虹风格的力导向关系图谱，帮助运维在大屏/复杂拓扑中快速定位故障。本次范围：**Phase 1 基础力导向图 + Phase 2 视觉特效**（不含业务交互与控制面板）。

## 决策（已与用户确认）

- **范围**：Phase 1+2——基础力导向图 + 全部特效（霓虹发光、离线呼吸灯、悬停聚焦淡化、延时联动粒子流、节点大小权重）
- **技术选型**：新装 `2d-force-graph`（原生支持粒子动画、Canvas 自绘、发光节点、呼吸灯）
- **入口**：顶部 tab 栏新建"拓扑图"页签，独立于"设备/外网/用户/备份"
- **分组节点**：`type=group` 照常显示为节点（中性灰），大小按子节点数
- **数据源**：复用 `useDevicesStore().tree`（30s 定时刷新自动同步），不新增后端接口
- **明确不做**：右键菜单/左键详情抽屉/搜索聚焦/物理参数控制面板/巡检交互/外网目标纳入

## 架构与组件

### 新文件 `frontend/src/utils/treeToGraph.js`

纯函数 `treeToGraph(tree)` → `{ nodes, links }`

- `nodes`：`{ id, name, type, status, latency_ms, ip_address, val }`
  - `val` = 子设备数 × 3 + 8（叶子设备 = 5，分组随子节点数增大）
  - `status`：分组节点强制 `'unknown'`（中性灰）
- `links`：`{ source: parentId, target: childId, status }`
- 递归遍历，独立可测

### 新文件 `frontend/src/components/TopologyView.vue`

- `import ForceGraph from '2d-force-graph'`，挂载到 ref 容器
- `const graphData = computed(() => treeToGraph(store.tree))`
- 用 `watch(graphData)` 更新 `fg.graphData(...)`
- 特效（全部实现）：
  - **节点外观**：`nodeCanvasObject` 自绘圆形 + `shadowBlur` 发光光晕
    - 在线 `#10b981`（翠绿）/ 警告 `#f59e0b`（琥珀）/ 离线 `#ef4444`（红）/ 未知 `#6b7280`（灰）
    - 分组节点未知色，半径为 `Math.max(4, Math.sqrt(val))` 缩放
  - **离线呼吸灯**：离线节点透明度随 `Date.now()/500` 正弦变化（明暗脉动）
  - **悬停聚焦**：`onNodeHover` 记录 `hoverNodeId`，非高亮节点/边透明度降至 `0.08`；高亮当前节点 + 直接相邻节点与边
  - **粒子流**：`linkDirectionalParticles` = 延时 ≤50 时 2 个 / 50-200 时 1 个 / >200 或 null 时 0 个；`linkDirectionalParticleSpeed` 高延时变慢；粒子颜色随延时（低青/高红）
  - **节点大小**：半径按 `val` 缩放（分组更大）
- 背景 `#0f172a`，宽度 100%，高度 `calc(100vh - 200px)`（扣除 header + tab 栏）
- 空树：显示空态提示文案
- 初始化/渲染异常：`try/catch` 显示错误文案

### 改动 `frontend/src/views/MainView.vue`

- 顶部 `<el-tabs>` 增加：

```html
<el-tab-pane label="拓扑图" name="topology">
  <el-card><TopologyView /></el-card>
</el-tab-pane>
```

- `import TopologyView from '../components/TopologyView.vue'`

### 测试

- `frontend/src/utils/__tests__/treeToGraph.spec.js`：
  1. 树打平为正确节点/链接（含分组 → unknown）
  2. `val` 权重正确（有子节点 > 叶子）
  3. 空树返回空
- `frontend/src/components/__tests__/TopologyView.spec.js`：
  4. mock `2d-force-graph`，验证组件挂载并调用 `graphData`
  5. 空树显示空态提示

## 依赖

- `npm install 2d-force-graph`

## 版本

- 发布 **0.4.3**

## 明确不做的（YAGNI）

- Phase 3 业务交互（右键菜单、详情抽屉、巡检/编辑/新增）
- Phase 4 控制面板（搜索聚焦、状态筛选、物理参数滑块）
- 外网目标纳入图谱
- 后端任何改动