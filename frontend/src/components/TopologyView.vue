<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ForceGraph from 'force-graph'
import { useDevicesStore } from '../stores/devices'
import { typeGlyph } from '../utils/deviceTypes'
import { treeToGraph, applyVisioHierarchicalLayout } from '../utils/treeToGraph'
import { getDeviceSnmpInterfaces } from '../api/devices'
import { SPEED_COLORS, getLinkColor } from '../utils/topologyLinks'
import { getVisioCanvasImage, preloadAllVisioCanvasImages } from '../utils/visioIcons'
import { exportFullTopologyImage } from '../utils/exportTopologyImage'
import { ElMessage } from 'element-plus'
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
const viewMode = ref(
  (typeof localStorage !== 'undefined' && localStorage.getItem('weaver_topology_view_mode')) || 'dark-neon'
)

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

function drawVisioNode(node, ctx) {
  const iconSize = 44
  const half = iconSize / 2
  const img = getVisioCanvasImage(node.type)
  if (img && img.src) {
    try {
      ctx.drawImage(img, node.x - half, node.y - half, iconSize, iconSize)
    } catch (e) {
      ctx.fillStyle = '#64748b'
      ctx.fillRect(node.x - half, node.y - half, iconSize, iconSize)
    }
  } else {
    ctx.fillStyle = '#64748b'
    ctx.fillRect(node.x - half, node.y - half, iconSize, iconSize)
  }

  // Top-right LED indicator
  const ledX = node.x + half - 4
  const ledY = node.y - half + 4
  const color = STATUS_COLORS[node.status] || '#94a3b8'
  const now = Date.now()
  let alpha = 1
  if (node.status === 'offline') {
    alpha = 0.4 + 0.6 * Math.abs(Math.sin(now / 500))
  }
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.beginPath()
  ctx.arc(ledX, ledY, 4.5, 0, 2 * Math.PI)
  ctx.fillStyle = color
  ctx.fill()
  ctx.lineWidth = 1.2
  ctx.strokeStyle = '#ffffff'
  ctx.stroke()
  ctx.restore()

  // Labels below
  if (showLabels.value || node.id === hoverNodeId.value) {
    ctx.save()
    ctx.font = `bold ${labelFontSize.value}px sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#1e293b'
    ctx.fillText(node.name, node.x, node.y + half + 4)

    if (node.ip_address) {
      ctx.font = `${Math.max(8, labelFontSize.value - 2)}px monospace`
      ctx.fillStyle = '#64748b'
      ctx.fillText(node.ip_address, node.x, node.y + half + 6 + labelFontSize.value)
    }
    ctx.restore()
  }
}

function nodeCanvasRenderer(node, ctx) {
  if (viewMode.value === 'classic-visio') {
    drawVisioNode(node, ctx)
  } else {
    drawNode(node, ctx)
  }
}

function getLinkStrokeColor(link) {
  if (link.status === 'offline') return '#ef4444'
  if (viewMode.value === 'classic-visio') {
    return '#94a3b8'
  }
  return getLinkColor(link, snmpSpeedMap.value)
}

function getParticleCount(link) {
  if (viewMode.value === 'classic-visio') return 0
  return particleCount(link)
}

function onViewModeChange(mode) {
  viewMode.value = mode
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('weaver_topology_view_mode', mode)
  }
  if (!fg) return
  if (mode === 'classic-visio') {
    fg.backgroundColor('#f8fafc')
    applyVisioHierarchicalLayout(graphData.value.nodes, graphData.value.links)
  } else {
    fg.backgroundColor('#0f172a')
    const fresh = treeToGraph(store.tree)
    graphData.value.nodes = fresh.nodes
  }
  syncGraphData()
  fg.zoomToFit?.(400, 30)
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

  const isVisio = viewMode.value === 'classic-visio'
  const pillBg = isVisio ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 23, 42, 0.85)'
  const sStroke = isVisio ? '#cbd5e1' : '#38bdf8'
  const sText = isVisio ? '#334155' : '#38bdf8'
  const tStroke = isVisio ? '#cbd5e1' : '#34d399'
  const tText = isVisio ? '#334155' : '#34d399'

  ctx.save()
  ctx.font = '9px monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  if (sPort) {
    const px = s.x + (t.x - s.x) * 0.22
    const py = s.y + (t.y - s.y) * 0.22
    const textWidth = ctx.measureText(sPort).width
    ctx.fillStyle = pillBg
    ctx.fillRect(px - textWidth / 2 - 3, py - 6, textWidth + 6, 12)
    ctx.strokeStyle = sStroke
    ctx.lineWidth = 0.8
    ctx.strokeRect(px - textWidth / 2 - 3, py - 6, textWidth + 6, 12)
    ctx.fillStyle = sText
    ctx.fillText(sPort, px, py)
  }

  if (tPort) {
    const px = s.x + (t.x - s.x) * 0.78
    const py = s.y + (t.y - s.y) * 0.78
    const textWidth = ctx.measureText(tPort).width
    ctx.fillStyle = pillBg
    ctx.fillRect(px - textWidth / 2 - 3, py - 6, textWidth + 6, 12)
    ctx.strokeStyle = tStroke
    ctx.lineWidth = 0.8
    ctx.strokeRect(px - textWidth / 2 - 3, py - 6, textWidth + 6, 12)
    ctx.fillStyle = tText
    ctx.fillText(tPort, px, py)
  }

  ctx.restore()
}

function renderGraph() {
  if (!graphEl.value || !graphData.value.nodes.length) return
  const bg = viewMode.value === 'classic-visio' ? '#f8fafc' : '#0f172a'
  if (viewMode.value === 'classic-visio') {
    applyVisioHierarchicalLayout(graphData.value.nodes, graphData.value.links)
  }
  fg = new ForceGraph(graphEl.value)
    .backgroundColor(bg)
    .graphData(graphData.value)
    .nodeRelSize(1)
    .nodeCanvasObjectMode(() => 'replace')
    .nodeCanvasObject(nodeCanvasRenderer)
    .linkCanvasObjectMode(() => 'after')
    .linkCanvasObject(drawLinkPortLabels)
    .linkColor(getLinkStrokeColor)
    .linkDirectionalParticles(getParticleCount)
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
  if (viewMode.value === 'classic-visio') {
    applyVisioHierarchicalLayout(graphData.value.nodes, graphData.value.links)
  }
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
  preloadAllVisioCanvasImages()
  if (viewMode.value === 'classic-visio' && graphData.value.nodes.length) {
    applyVisioHierarchicalLayout(graphData.value.nodes, graphData.value.links)
  }
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

async function onExportImage() {
  if (!graphData.value.nodes.length) return
  const success = await exportFullTopologyImage(graphData.value.nodes, graphData.value.links)
  if (typeof ElMessage !== 'undefined') {
    if (success) {
      ElMessage.success?.('拓扑高清图片已成功生成并下载')
    } else {
      ElMessage.error?.('导出拓扑高清图片失败')
    }
  }
}
</script>

<template>
  <div ref="wrapEl" class="topology-wrap" :class="{ fullscreen: isFullscreen, 'classic-visio': viewMode === 'classic-visio' }">
    <div v-if="error" class="error">{{ error }}</div>
    <template v-else-if="graphData.nodes.length">
      <div class="topo-toolbar">
        <el-radio-group v-model="viewMode" size="small" class="mode-switcher" @change="onViewModeChange">
          <el-radio-button value="dark-neon">🌌 暗黑霓虹</el-radio-button>
          <el-radio-button value="classic-visio">📐 经典 Visio</el-radio-button>
        </el-radio-group>

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
          LLDP / 物理拓扑探测
        </el-button>

        <el-button
          size="small"
          :loading="isSnmpLoading"
          class="refresh-btn"
          @click="fetchSnmpLinkSpeeds"
        >
          刷新链路
        </el-button>

        <el-button
          size="small"
          class="export-btn"
          @click="onExportImage"
        >
          📷 导出图片
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
.topology-wrap.classic-visio {
  background: #f8fafc;
}
.topology-wrap.classic-visio .topo-toolbar {
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  color: #475569;
}
.topology-wrap.classic-visio .topo-toolbar .label {
  color: #334155;
}
.topology-wrap.classic-visio .legend-group {
  color: #475569;
}
.topology-wrap.classic-visio .back-home {
  color: #64748b;
}
.topology-wrap.classic-visio .back-home:hover {
  color: #0f172a;
}
.topology-wrap.classic-visio .graph {
  background-color: #f8fafc;
  background-image: 
    linear-gradient(#e2e8f0 1px, transparent 1px),
    linear-gradient(90deg, #e2e8f0 1px, transparent 1px);
  background-size: 25px 25px;
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