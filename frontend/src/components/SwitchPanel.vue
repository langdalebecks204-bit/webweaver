<template>
  <div class="switch-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span class="device-name">{{ deviceName }}</span>
        <el-tag size="small" type="success" effect="dark">SNMP Active</el-tag>
      </div>

      <!-- Speed Color Legend (Consistent with Topology) -->
      <div class="speed-legend">
        <span class="legend-item"><span class="legend-dot speed-100m" />百兆</span>
        <span class="legend-item"><span class="legend-dot speed-1000m" />千兆</span>
        <span class="legend-item"><span class="legend-dot speed-2500m" />2.5G</span>
        <span class="legend-item"><span class="legend-dot speed-10000m" />万兆</span>
      </div>

      <div class="panel-summary">
        <span>Up: <b class="up-count">{{ upCount }}</b></span>
        <el-divider direction="vertical" />
        <span>Down: <b class="down-count">{{ downCount }}</b></span>
        <el-divider direction="vertical" />
        <span>总端口: <b>{{ interfaces.length }}</b></span>
      </div>
    </div>

    <!-- Ethernet RJ45 Ports Matrix -->
    <div class="ports-grid">
      <div
        v-for="port in interfaces"
        :key="port.if_index"
        class="port-item"
        :class="[
          port.status,
          getSpeedClass(port.speed_mbps, port.status),
          { selected: selectedPortIndex === port.if_index }
        ]"
        :style="{ '--speed-color': getSpeedColor(port.speed_mbps, port.status) }"
        @click="$emit('select-port', port)"
      >
        <div class="port-jack">
          <div
            class="led-light"
            :class="[port.status, getSpeedClass(port.speed_mbps, port.status)]"
            :style="{ backgroundColor: getSpeedColor(port.speed_mbps, port.status) }"
          ></div>
          <div class="port-number">{{ port.if_index }}</div>
        </div>
        <div class="port-tooltip">
          <div class="tooltip-title">{{ port.name }} ({{ port.status.toUpperCase() }})</div>
          <div v-if="port.custom_description" class="tooltip-desc">{{ port.custom_description }}</div>
          <div class="tooltip-speed">
            速率: <span class="speed-val" :style="{ color: getSpeedColor(port.speed_mbps, port.status) }">
              {{ getSpeedText(port.speed_mbps, port.status) }}
            </span>
          </div>
          <div>In: {{ port.in_rate_text }}</div>
          <div>Out: {{ port.out_rate_text }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { SPEED_COLORS } from '../utils/topologyLinks'

const props = defineProps({
  deviceName: {
    type: String,
    default: 'Switch'
  },
  interfaces: {
    type: Array,
    default: () => []
  },
  selectedPortIndex: {
    type: Number,
    default: null
  }
})

defineEmits(['select-port'])

const upCount = computed(() => props.interfaces.filter(i => i.status === 'up').length)
const downCount = computed(() => props.interfaces.filter(i => i.status !== 'up').length)

function getSpeedColor(speedMbps, status) {
  if (status !== 'up') return '#718096'
  const speed = Number(speedMbps) || 0
  if (speed >= 10000) return SPEED_COLORS[10000] // 万兆: #3b82f6 (蓝)
  if (speed >= 2500) return SPEED_COLORS[2500]   // 2.5G: #39ff14 (荧光绿)
  if (speed >= 1000) return SPEED_COLORS[1000]   // 千兆: #10b981 (绿)
  if (speed >= 100) return SPEED_COLORS[100]     // 百兆: #f97316 (橙)
  if (speed > 0) return '#eab308'               // 十兆: 黄
  return SPEED_COLORS[1000]                      // 默认在线绿
}

function getSpeedClass(speedMbps, status) {
  if (status !== 'up') return 'speed-down'
  const speed = Number(speedMbps) || 0
  if (speed >= 10000) return 'speed-10000m'
  if (speed >= 2500) return 'speed-2500m'
  if (speed >= 1000) return 'speed-1000m'
  if (speed >= 100) return 'speed-100m'
  return 'speed-1000m'
}

function getSpeedText(speedMbps, status) {
  if (status !== 'up') return 'N/A'
  const s = Number(speedMbps) || 0
  if (s >= 10000) return `${s} Mbps (万兆)`
  if (s >= 2500) return `${s} Mbps (2.5G)`
  if (s >= 1000) return `${s} Mbps (千兆)`
  if (s >= 100) return `${s} Mbps (百兆)`
  if (s > 0) return `${s} Mbps`
  return '已连接'
}
</script>

<style scoped>
.switch-panel {
  background: #1e222d;
  border-radius: 8px;
  padding: 16px;
  color: #e0e6ed;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  margin-bottom: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
  border-bottom: 1px solid #2d3342;
  padding-bottom: 10px;
}

.device-name {
  font-size: 16px;
  font-weight: 600;
  margin-right: 10px;
}

.speed-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: #a0aec0;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.legend-dot.speed-100m {
  background: #f97316;
  box-shadow: 0 0 5px #f97316;
}

.legend-dot.speed-1000m {
  background: #10b981;
  box-shadow: 0 0 5px #10b981;
}

.legend-dot.speed-2500m {
  background: #39ff14;
  box-shadow: 0 0 5px #39ff14;
}

.legend-dot.speed-10000m {
  background: #3b82f6;
  box-shadow: 0 0 5px #3b82f6;
}

.panel-summary {
  font-size: 13px;
  color: #a0aec0;
}

.up-count {
  color: #48bb78;
}

.down-count {
  color: #a0aec0;
}

.ports-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
  gap: 10px;
}

.port-item {
  position: relative;
  background: #2a303c;
  border: 1px solid #3a4253;
  border-radius: 6px;
  padding: 8px 4px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.port-item.up {
  border-top: 3px solid var(--speed-color, #10b981);
}

.port-item:hover, .port-item.selected {
  border-color: #4299e1;
  background: #333b4b;
  transform: translateY(-2px);
}

.port-jack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.led-light {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #718096;
  box-shadow: 0 0 2px #718096;
  transition: all 0.3s ease;
}

.led-light.up {
  box-shadow: 0 0 7px var(--speed-color, #10b981);
}

.port-number {
  font-size: 12px;
  font-weight: bold;
  color: #cbd5e0;
}

/* Hover Tooltip */
.port-tooltip {
  display: none;
  position: absolute;
  bottom: 110%;
  left: 50%;
  transform: translateX(-50%);
  background: #1a202c;
  border: 1px solid #4a5568;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 11px;
  white-space: nowrap;
  z-index: 100;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
  text-align: left;
}

.port-item:hover .port-tooltip {
  display: block;
}

.tooltip-title {
  font-weight: bold;
  color: #63b3ed;
  margin-bottom: 4px;
}

.tooltip-desc {
  color: #f6ad55;
  font-weight: 500;
  margin-bottom: 4px;
}

.tooltip-speed {
  margin-bottom: 4px;
}

.speed-val {
  font-weight: 600;
}
</style>
