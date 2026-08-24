<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ForceGraph from 'force-graph'
import { useDevicesStore } from '../stores/devices'
import { typeGlyph } from '../utils/deviceTypes'
import { treeToGraph } from '../utils/treeToGraph'

const store = useDevicesStore()
const graphEl = ref(null)
const wrapEl = ref(null)
const error = ref('')
const hoverNodeId = ref(null)
const labelFontSize = ref(6)
const showLabels = ref(true)
const isFullscreen = ref(false)

const emit = defineEmits(['back-home'])

function toggleFullscreen() {
  const el = wrapEl.value
  if (!el) return
  if (!document.fullscreenElement) {
    el.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}

function onFsChange() {
  isFullscreen.value = document.fullscreenElement === wrapEl.value
}

function backHome() {
  if (document.fullscreenElement) document.exitFullscreen?.()
  emit('back-home')
}

const graphData = computed(() => treeToGraph(store.tree))

const STATUS_COLORS = {
  online: '#10b981',
  warning: '#f59e0b',
  offline: '#ef4444',
  unknown: '#6b7280',
}

let fg = null
let resizeObserver = null

function syncSize() {
  if (!fg || !graphEl.value) return
  const w = graphEl.value.clientWidth
  const h = graphEl.value.clientHeight
  if (!w || !h) return
  fg.width(w).height(h)
}

function particleCount(link) {
  const target = link.target
  const lat = target.latency_ms
  if (lat == null) return 0
  if (lat <= 50) return 2
  if (lat <= 200) return 1
  return 0
}

function particleSpeed(link) {
  const lat = link.target.latency_ms
  if (lat == null) return 0
  if (lat <= 50) return 0.02
  if (lat <= 200) return 0.01
  return 0.005
}

function particleColor(link) {
  const lat = link.target.latency_ms
  if (lat == null) return '#6b7280'
  if (lat <= 50) return '#34d399'
  if (lat <= 200) return '#fbbf24'
  return '#ef4444'
}

function isHighlighted(node) {
  if (hoverNodeId.value == null) return true
  if (node.id === hoverNodeId.value) return true
  return graphData.value.links.some(
    (l) =>
      (l.source.id === hoverNodeId.value && l.target.id === node.id) ||
      (l.target.id === hoverNodeId.value && l.source.id === node.id)
  )
}

function drawNode(node, ctx) {
  const r = Math.max(8, Math.sqrt(node.val))
  const color = STATUS_COLORS[node.status] || '#6b7280'
  const now = Date.now()
  let alpha = isHighlighted(node) ? 1 : 0.08
  if (node.status === 'offline' && isHighlighted(node)) {
    alpha = 0.5 + 0.5 * Math.abs(Math.sin(now / 500))
  }
  ctx.globalAlpha = alpha
  ctx.beginPath()
  ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false)
  ctx.fillStyle = color
  ctx.shadowColor = color
  ctx.shadowBlur = node.status === 'unknown' ? 4 : 14
  ctx.fill()
  ctx.shadowBlur = 0
  ctx.globalAlpha = 1
  ctx.fillStyle = 'rgba(255,255,255,0.92)'
  ctx.font = '10px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(typeGlyph(node.type), node.x, node.y)
  ctx.textBaseline = 'alphabetic'
  if (showLabels.value || node.id === hoverNodeId.value) {
    ctx.fillStyle = 'rgba(255,255,255,0.85)'
    ctx.font = `${labelFontSize.value}px sans-serif`
    ctx.textAlign = 'center'
    ctx.fillText(node.name, node.x, node.y - r - 4)
  }
}

function renderGraph() {
  if (!graphEl.value || !graphData.value.nodes.length) return
  fg = new ForceGraph(graphEl.value)
    .backgroundColor('#0f172a')
    .graphData(graphData.value)
    .nodeRelSize(1)
    .nodeCanvasObjectMode(() => 'replace')
    .nodeCanvasObject(drawNode)
    .linkColor(() => 'rgba(148,163,184,0.6)')
    .linkDirectionalParticles(particleCount)
    .linkDirectionalParticleSpeed(particleSpeed)
    .linkDirectionalParticleWidth(2)
    .linkDirectionalParticleColor(particleColor)
    .onNodeHover((node) => {
      hoverNodeId.value = node ? node.id : null
    })
    .width(graphEl.value.clientWidth)
    .height(graphEl.value.clientHeight)
  if (!resizeObserver && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(syncSize)
    resizeObserver.observe(graphEl.value)
  }
}

const NODE_FIELDS = ['name', 'type', 'status', 'latency_ms', 'ip_address', 'val']

function syncGraphData() {
  if (!fg || !graphData.value.nodes.length) return
  const prevNodes = fg.graphData().nodes || []
  const byId = new Map(prevNodes.map((n) => [n.id, n]))
  const nodes = graphData.value.nodes.map((n) => {
    const old = byId.get(n.id)
    if (old) {
      for (const f of NODE_FIELDS) old[f] = n[f]
      return old
    }
    return { ...n }
  })
  const links = graphData.value.links.map((l) => ({ source: l.source, target: l.target }))
  fg.graphData({ nodes, links })
}

watch(
  graphData,
  async () => {
    if (!graphData.value.nodes.length) return
    await nextTick()
    try {
      if (fg) syncGraphData()
      else renderGraph()
    } catch (e) {
      error.value = `图谱初始化失败：${e.message}`
    }
  }
)

onMounted(async () => {
  document.addEventListener('fullscreenchange', onFsChange)
  await nextTick()
  try {
    renderGraph()
  } catch (e) {
    error.value = `图谱初始化失败：${e.message}`
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFsChange)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (fg) {
    fg.destroy()
    fg = null
  }
})
</script>

<template>
  <div ref="wrapEl" class="topology-wrap" :class="{ fullscreen: isFullscreen }">
    <div v-if="error" class="error">{{ error }}</div>
    <template v-else-if="graphData.nodes.length">
      <div class="topo-toolbar">
        <span class="label">字号</span>
        <el-slider
          v-model="labelFontSize"
          :min="6"
          :max="18"
          :step="1"
          class="font-slider"
        />
        <span class="label">显示标签</span>
        <el-switch v-model="showLabels" />
        <a v-if="isFullscreen" class="back-home" href="#" @click.prevent="backHome">← 返回主页</a>
        <el-button size="small" class="fullscreen-btn" @click="toggleFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </el-button>
      </div>
      <div ref="graphEl" class="graph" />
    </template>
    <div v-else class="empty">暂无设备</div>
  </div>
</template>

<style scoped>
.topology-wrap {
  width: 100%;
  height: calc(100vh - 200px);
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}
.topology-wrap:fullscreen {
  height: 100vh;
  border-radius: 0;
}
.back-home {
  margin-left: auto;
  color: #94a3b8;
  font-size: 13px;
  text-decoration: none;
  white-space: nowrap;
}
.back-home:hover {
  color: #e2e8f0;
}
.topo-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  color: #94a3b8;
  background: #111c31;
  border-bottom: 1px solid #1e293b;
}
.topo-toolbar .label {
  font-size: 13px;
  white-space: nowrap;
}
.topo-toolbar .font-slider {
  width: 160px;
  margin: 0 8px;
}
.topo-toolbar .fullscreen-btn {
  margin-left: auto;
}
.graph {
  flex: 1;
  width: 100%;
  min-height: 0;
}
.error {
  color: #ef4444;
  padding: 24px;
}
.empty {
  color: #94a3b8;
  padding: 24px;
}
</style>