<template>
  <div class="switch-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span class="device-name">{{ deviceName }}</span>
        <el-tag size="small" type="success" effect="dark">SNMP Active</el-tag>
      </div>
      <div class="panel-summary">
        <span>Up: <b class="up-count">{{ upCount }}</b></span>
        <el-divider direction="vertical" />
        <span>Down: <b class="down-count">{{ downCount }}</b></span>
        <el-divider direction="vertical" />
        <span>Total Ports: <b>{{ interfaces.length }}</b></span>
      </div>
    </div>

    <!-- Ethernet RJ45 Ports Matrix -->
    <div class="ports-grid">
      <div
        v-for="port in interfaces"
        :key="port.if_index"
        class="port-item"
        :class="[port.status, { selected: selectedPortIndex === port.if_index }]"
        @click="$emit('select-port', port)"
      >
        <div class="port-jack">
          <div class="led-light" :class="port.status"></div>
          <div class="port-number">{{ port.if_index }}</div>
        </div>
        <div class="port-tooltip">
          <div class="tooltip-title">{{ port.name }} ({{ port.status.toUpperCase() }})</div>
          <div>Speed: {{ port.speed_mbps ? port.speed_mbps + ' Mbps' : 'N/A' }}</div>
          <div>In: {{ port.in_rate_text }}</div>
          <div>Out: {{ port.out_rate_text }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

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
  margin-bottom: 14px;
  border-bottom: 1px solid #2d3342;
  padding-bottom: 10px;
}

.device-name {
  font-size: 16px;
  font-weight: 600;
  margin-right: 10px;
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
}

.led-light.up {
  background-color: #48bb78;
  box-shadow: 0 0 6px #48bb78;
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
</style>
