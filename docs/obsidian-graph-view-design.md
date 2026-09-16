# WebWeaver 拓扑关系图谱（Obsidian Graph View 风格）设计方案

本方案旨在为 WebWeaver 网络状态检测平台设计一套基于 **Obsidian Graph View** 风格的拓扑关系图谱功能，用于在后续更新中提升大屏可视化与网络故障定位体验。

---

## 1. 核心视觉与交互特色

### 1.1 节点外观与暗黑霓虹风格 (Status Glow & Pulse)
- **暗黑极简背景**：采用 `#0f172a` 或 `#0d1117` 主题色，匹配大屏科技感。
- **在线节点（Online）**：翠绿/青色发光光晕（`#10b981`），代表设备响应正常。
- **警示节点（Warning）**：琥珀黄/橙色微光（`#f59e0b`），代表 ICMP Ping 正常但 TCP 端口异常。
- **离线节点（Offline）**：璀璨红脉冲光圈（`#ef4444`），并在拓扑图中呈呼吸灯闪烁。
- **未知节点（Unknown）**：暗灰隐身节点（`#6b7280`）。
- **节点大小（Weight）**：根据设备的权重或连接子设备数量动态缩放，根节点/网关最大。

### 1.2 悬停高光与聚焦路径 (Focus & Neighbor Highlighting)
- 鼠标悬停在某个设备节点上时，**自动淡化所有非相关节点与连线**，仅亮起当前设备及其上下游直接相连的拓扑链路。
- 帮助运维人员在复杂拓扑中瞬间定位受影响的整个下游设备分支。

### 1.3 延时流向粒子动画 (Link Data Flow Particles)
- 在拓扑边上绘制沿连线方向移动的数据流光点粒子。
- **延时联动**：根据设备的 ICMP 延时（Latency）调整粒子流动速度与颜色（高延时变慢/变红），直观展示网络传输健康度。

---

## 2. 前端技术选型

推荐方案：**`force-graph` / `2d-force-graph`** (基于 HTML5 Canvas / d3-force)

- **推荐理由**：
  1. 目前最贴近 Obsidian 关系图谱物理引擎与拖拽碰撞效果的开源库。
  2. 原生支持连线方向粒子动画（`linkDirectionalParticles`）。
  3. 支持 Canvas 自定义节点发光与多层绘制，千级节点下依然能保持 60 FPS 流畅度。
  4. 原生兼容 Vue 3 声明式生命周期。

---

## 3. 数据转换逻辑 (Tree to Graph)

WebWeaver 当前接口 `/api/devices/tree` 返回嵌套 JSON 树，可在前端通过递归打平为 Graph 格式：

```typescript
interface GraphNode {
  id: number;
  name: string;
  ip: string;
  status: 'online' | 'warning' | 'offline' | 'unknown';
  latency: number;
  val: number; // 节点大小权重
}

interface GraphLink {
  source: number;
  target: number;
  status: string;
}

function transformTreeToGraph(treeData: any[]): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];

  function traverse(node: any, parentId: number | null = null) {
    nodes.push({
      id: node.id,
      name: node.name,
      ip: node.ip,
      status: node.status || 'unknown',
      latency: node.avg_latency || 0,
      val: node.children?.length ? (node.children.length * 3 + 8) : 5,
    });

    if (parentId !== null) {
      links.push({
        source: parentId,
        target: node.id,
        status: node.status,
      });
    }

    if (node.children && node.children.length > 0) {
      node.children.forEach((child: any) => traverse(child, node.id));
    }
  }

  treeData.forEach(root => traverse(root));
  return { nodes, links };
}
```

---

## 4. 控制面板与图谱交互设计

### 4.1 Obsidian 悬浮控制面板 (Glassmorphism Control Drawer)
- **搜索与聚焦**：输入设备名称或 IP，搜索命中节点居中高亮并平滑放大。
- **过滤器**：一键切换 [ 显示全部 / 仅显示告警设备 ]。
- **物理参数滑动条**：
  - Repulsion Force（节点斥力）
  - Link Distance（边拉力距离）
  - Center Gravity（向心引力）

### 4.2 设备节点右键菜单 (Context Menu Integration)
- **左键单击**：侧边弹出设备详情（实时延时、端口状态、最近 24 小时历史趋势折线图）。
- **右键单击**：弹出快捷菜单：
  - ⚡ **立即巡检该节点及子树** (`POST /api/devices/{id}/recheck`)
  - 📊 **查看巡检历史** (`GET /api/devices/{id}/history`)
  - ✏️ **编辑设备**
  - ➕ **新增子设备**

---

## 5. 建议实施路线图 (Implementation Roadmap)

1. **Phase 1 原型搭建**：安装 `force-graph`，新建拓扑关系图页面组件，实现基础力导向图展示。
2. **Phase 2 特效增强**：实现暗黑霓虹发光节点、离线呼吸灯脉冲、延时粒子流动画。
3. **Phase 3 业务交互联动**：集成设备右键菜单、左键抽屉面板与实时巡检触发。
4. **Phase 4 大屏与控制面板**：增加 Obsidian 风格的控制面板（物理参数调节、搜索高亮、状态筛选）。
