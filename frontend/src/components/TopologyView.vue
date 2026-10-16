<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ForceGraph from 'force-graph'
import { useDevicesStore } from '../stores/devices'
import { typeGlyph } from '../utils/deviceTypes'
import { treeToGraph } from '../utils/treeToGraph'
import { getDeviceSnmpInterfaces } from '../api/devices'
import { SPEED_COLORS, getLinkColor } from '../utils/topologyLinks'
import LldpDiscoveryModal from './LldpDiscoveryModal.vue'

const store = useDevicesStore()
const graphEl = ref(null)
const wrapEl = ref(null)
const error = ref('')
const hoverNodeId = ref(null)
const labelFontSize = ref(10)
const showLabels = ref(true)
const showPortLabels = ref(true)
const lldpModalVisible = ref(false)
const isFullscreen = ref(false)
const snmpSpeedMap = ref(new Map())
const isSnmpLoading = ref(false)

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
  return getLinkColor(link, snmpSpeedMap.value)
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
  const isCore = node.layer === 0 || (node.type === 'switch' && (node.name?.includes('核心') || node.id === graphData.value.coreNodeId))
  const baseR = isCore ? 26 : (node.type === 'switch' || node.type === 'router' ? 22 : 18)
  const r = Math.max(baseR, Math.sqrt(node.val || 8) * 1.6)
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
  ctx.shadowBlur = node.status === 'unknown' ? 4 : 16
  ctx.fill()
  ctx.shadowBlur = 0
  ctx.globalAlpha = 1
  ctx.fillStyle = 'rgba(255,255,255,0.95)'
  const iconSize = Math.round(r * 0.95)
  ctx.font = `${iconSize}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(typeGlyph(node.type), node.x, node.y)
  ctx.textBaseline = 'alphabetic'
  if (showLabels.value || node.id === hoverNodeId.value) {
    ctx.fillStyle = 'rgba(255,255,255,0.9)'
    ctx.font = `${labelFontSize.value}px sans-serif`
    ctx.textAlign = 'center'
    ctx.fillText(node.name, node.x, node.y - r - 6)
  }
}

let snmpDebounceTimer = null

async function fetchSnmpLinkSpeeds() {
  if (!graphData.value.nodes.length || isSnmpLoading.value) return
  isSnmpLoading.value = true
  try {
    const swNodes = graphData.value.nodes.filter(
      (n) =>
        (n.type === 'switch' || n.type === 'router') &&
        n.ip_address &&
        n.snmp_enabled !== false &&
        n.status !== 'offline'
    )
    if (!swNodes.length) return
    const results = await Promise.allSettled(
      swNodes.map(async (sw) => {
        const res = await getDeviceSnmpInterfaces(sw.id)
        return { swId: sw.id, interfaces: res.data?.interfaces || [] }
      })
    )
    const map = new Map()
    for (const r of results) {
      if (r.status === 'fulfilled' && r.value) {
        const { swId, interfaces } = r.value
        for (const iface of interfaces) {
          const targetId = iface.binding?.target_id
          if (targetId) {
            map.set(`${swId}->${targetId}`, iface.speed_mbps || 0)
          }
        }
      }
    }
    snmpSpeedMap.value = map
  } catch (err) {
    console.error('Failed to fetch snmp link speeds', err)
  } finally {
    isSnmpLoading.value = false
  }
}

function queueFetchSnmpLinkSpeeds() {
  if (snmpDebounceTimer) clearTimeout(snmpDebounceTimer)
  snmpDebounceTimer = setTimeout(() => {
    fetchSnmpLinkSpeeds()
  }, 1000)
}

function drawLinkPortLabels(link, ctx) {
  if (!showPortLabels.value) return
  const s = link.source
  const t = link.target
  if (typeof s !== 'object' || typeof t !== 'object') return
  if (s.x === undefined || t.x === undefined) return

  const sPort = link.source_port
  const tPort = link.target_port
  if (!sPort && !tPort) return

  ctx.save()
  ctx.font = '9px monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  if (sPort) {
    const px = s.x + (t.x - s.x) * 0.22
    const py = s.y + (t.y - s.y) * 0.22
    const textWidth = ctx.measureText(sPort).width
    ctx.fillStyle = 'rgba(15, 23, 42, 0.85)'
    ctx.fillRect(px - textWidth / 2 - 3, py - 6, textWidth + 6, 12)
    ctx.strokeStyle = '#38bdf8'
    ctx.lineWidth = 0.8
    ctx.strokeRect(px - textWidth / 2 - 3, py - 6, textWidth + 6, 12)
    ctx.fillStyle = '#38bdf8'
    ctx.fillText(sPort, px, py)
  }

  if (tPort) {
    const px = s.x + (t.x - s.x) * 0.78
    const py = s.y + (t.y - s.y) * 0.78
    const textWidth = ctx.measureText(tPort).width
    ctx.fillStyle = 'rgba(15, 23, 42, 0.85)'
    ctx.fillRect(px - textWidth / 2 - 3, py - 6, textWidth + 6, 12)
    ctx.strokeStyle = '#34d399'
    ctx.lineWidth = 0.8
    ctx.strokeRect(px - textWidth / 2 - 3, py - 6, textWidth + 6, 12)
    ctx.fillStyle = '#34d399'
    ctx.fillText(tPort, px, py)
  }

  ctx.restore()
}

function renderGraph() {
  if (!graphEl.value || !graphData.value.nodes.length) return
  fg = new ForceGraph(graphEl.value)
    .backgroundColor('#0f172a')
    .graphData(graphData.value)
    .nodeRelSize(1)
    .nodeCanvasObjectMode(() => 'replace')
    .nodeCanvasObject(drawNode)
    .linkCanvasObjectMode(() => 'after')
    .linkCanvasObject(drawLinkPortLabels)
    .linkColor((link) => getLinkColor(link, snmpSpeedMap.value))
    .linkDirectionalParticles(particleCount)
    .linkDirectionalParticleSpeed(particleSpeed)
    .linkDirectionalParticleWidth(2)
    .linkDirectionalParticleColor(particleColor)
    .onNodeHover((node) => {
      hoverNodeId.value = node ? node.id : null
    })
    .width(graphEl.value.clientWidth)
    .height(graphEl.value.clientHeight)

  fg.centerAt?.(0, 0, 400)
  fg.zoomToFit?.(400, 30)

  if (!resizeObserver && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(syncSize)
    resizeObserver.observe(graphEl.value)
  }
}

const NODE_FIELDS = ['name', 'type', 'status', 'latency_ms', 'ip_address', 'val', 'fx', 'fy', 'layer', 'port_bindings']

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
  const links = graphData.value.links.map((l) => ({
    source: l.source,
    target: l.target,
    status: l.status,
    source_port: l.source_port,
    target_port: l.target_port,
  }))
  fg.graphData({ nodes, links })
  fg.centerAt?.(0, 0, 400)
  fg.zoomToFit?.(400, 30)
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
    queueFetchSnmpLinkSpeeds()
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
  queueFetchSnmpLinkSpeeds()
})

onBeforeUnmount(() => {
  if (snmpDebounceTimer) {
    clearTimeout(snmpDebounceTimer)
    snmpDebounceTimer = null
  }
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

        <span class="label">显示端口</span>
        <el-switch v-model="showPortLabels" />

        <div class="legend-group">
          <span class="legend-item"><span class="legend-dot offline" />离线</span>
          <span class="legend-item"><span class="legend-dot speed-100m" />百兆</span>
          <span class="legend-item"><span class="legend-dot speed-1000m" />千兆</span>
          <span class="legend-item"><span class="legend-dot speed-2500m" />2.5G</span>
          <span class="legend-item"><span class="legend-dot speed-10000m" />万兆</span>
          <span class="legend-item"><span class="legend-dot unknown" />未知</span>
        </div>

        <el-button
          size="small"
          type="primary"
          plain
          class="lldp-btn"
          @click="lldpModalVisible = true"
        >
          LLDP 拓扑探测
        </el-button>

        <el-button
          size="small"
          :loading="isSnmpLoading"
          class="refresh-btn"
          @click="fetchSnmpLinkSpeeds"
        >
          刷新链路
        </el-button>

        <a v-if="isFullscreen" class="back-home" href="#" @click.prevent="backHome">← 返回主页</a>
        <el-button size="small" class="fullscreen-btn" @click="toggleFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </el-button>
      </div>
      <div ref="graphEl" class="graph" />
    </template>
    <div v-else class="empty">暂无设备</div>

    <LldpDiscoveryModal
      v-model="lldpModalVisible"
      @applied="queueFetchSnmpLinkSpeeds"
    />
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
  flex-wrap: wrap;
}
.topo-toolbar .label {
  font-size: 13px;
  white-space: nowrap;
}
.topo-toolbar .font-slider {
  width: 140px;
  margin: 0 8px;
}
.legend-group {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: 8px;
  padding: 2px 8px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 6px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #cbd5e1;
  white-space: nowrap;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.legend-dot.offline {
  background: #ef4444;
}
.legend-dot.speed-100m {
  background: #f97316;
}
.legend-dot.speed-1000m {
  background: #10b981;
}
.legend-dot.speed-2500m {
  background: #39ff14;
}
.legend-dot.speed-10000m {
  background: #3b82f6;
}
.legend-dot.unknown {
  background: #94a3b8;
}
.refresh-btn {
  margin-left: 6px;
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