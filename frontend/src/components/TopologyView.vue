<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ForceGraph from 'force-graph'
import { useDevicesStore } from '../stores/devices'
import { treeToGraph } from '../utils/treeToGraph'

const store = useDevicesStore()
const graphEl = ref(null)
const error = ref('')
const hoverNodeId = ref(null)

const graphData = computed(() => treeToGraph(store.tree))

const STATUS_COLORS = {
  online: '#10b981',
  warning: '#f59e0b',
  offline: '#ef4444',
  unknown: '#6b7280',
}

let fg = null

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
  const r = Math.max(4, Math.sqrt(node.val))
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
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.font = '12px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText(node.name, node.x, node.y - r - 4)
}

function renderGraph() {
  if (!graphEl.value || !graphData.value.nodes.length) return
  if (fg) {
    fg.graphData(graphData.value)
    return
  }
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
      if (node) {
        fg.graphData(graphData.value)
      }
    })
    .width(graphEl.value.clientWidth)
    .height(graphEl.value.clientHeight)
}

watch(
  () => graphData.value.nodes.length,
  async () => {
    if (!graphData.value.nodes.length) return
    await nextTick()
    try {
      renderGraph()
    } catch (e) {
      error.value = `图谱初始化失败：${e.message}`
    }
  }
)

onMounted(async () => {
  await nextTick()
  try {
    renderGraph()
  } catch (e) {
    error.value = `图谱初始化失败：${e.message}`
  }
})

onBeforeUnmount(() => {
  if (fg) {
    fg.destroy()
    fg = null
  }
})
</script>

<template>
  <div class="topology-wrap">
    <div v-if="error" class="error">{{ error }}</div>
    <div v-else-if="!graphData.nodes.length" class="empty">暂无设备</div>
    <div v-else ref="graphEl" class="graph" />
  </div>
</template>

<style scoped>
.topology-wrap {
  width: 100%;
  height: calc(100vh - 200px);
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
}
.graph {
  width: 100%;
  height: 100%;
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