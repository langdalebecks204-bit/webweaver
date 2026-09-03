<template>
  <el-dialog
    v-model="visible"
    :title="`交换机端口与实时带宽监控 - ${device?.name || ''}`"
    width="900px"
    destroy-on-close
    @closed="onClose"
  >
    <div v-loading="loading" class="snmp-container">
      <template v-if="device && interfaces.length > 0">
        <!-- Physical Switch Visual Panel -->
        <SwitchPanel
          :device-name="device.name"
          :interfaces="interfaces"
          :selected-port-index="selectedPort?.if_index"
          @select-port="handleSelectPort"
        />

        <!-- Controls Toolbar -->
        <div class="toolbar">
          <div class="left-tools">
            <el-tag type="info">最后刷新: {{ lastUpdated }}</el-tag>
          </div>
          <div class="right-tools">
            <el-switch
              v-model="autoRefresh"
              active-text="自动刷新 (5s)"
              @change="toggleAutoRefresh"
            />
            <el-button type="primary" size="small" :icon="Refresh" @click="fetchData">
              手动刷新
            </el-button>
          </div>
        </div>

        <!-- Realtime Bandwidth ECharts Graph for Selected Port -->
        <div v-if="selectedPort" class="chart-section">
          <div class="chart-header">
            <h4>端口带宽实时趋势: {{ selectedPort.name }}</h4>
            <div class="chart-rates">
              <span class="rate-in">入向: {{ selectedPort.in_rate_text }}</span>
              <span class="rate-out">出向: {{ selectedPort.out_rate_text }}</span>
            </div>
          </div>
          <div ref="chartRef" class="echarts-box"></div>
        </div>

        <!-- Interfaces Table -->
        <div class="table-section">
          <el-table
            :data="interfaces"
            height="260"
            stripe
            size="small"
            highlight-current-row
            @current-change="handleSelectPort"
          >
            <el-table-column prop="if_index" label="端口" width="70" align="center" />
            <el-table-column prop="name" label="接口名称" min-width="120" />
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'up' ? 'success' : 'info'" size="small">
                  {{ row.status.toUpperCase() }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="速率" width="100" align="center">
              <template #default="{ row }">
                {{ row.speed_mbps ? row.speed_mbps + ' Mbps' : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="in_rate_text" label="实时入向带宽" min-width="130" align="right" />
            <el-table-column prop="out_rate_text" label="实时出向带宽" min-width="130" align="right" />
          </el-table>
        </div>
      </template>

      <!-- Empty / Error state -->
      <el-empty v-else-if="!loading" description="未能获取到交换机 SNMP 接口信息，请确认交换机是否已启用 SNMP服务" />
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getDeviceSnmpInterfaces } from '../api/devices'
import SwitchPanel from './SwitchPanel.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  device: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const loading = ref(false)
const interfaces = ref([])
const selectedPort = ref(null)
const autoRefresh = ref(false)
const lastUpdated = ref('-')
const chartRef = ref(null)

let timer = null
let chartInstance = null
const trafficHistory = {} // port_idx -> { time: [], in_kbps: [], out_kbps: [] }

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val && props.device?.id) {
    interfaces.value = []
    selectedPort.value = null
    fetchData()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function toggleAutoRefresh(val) {
  if (val) {
    timer = setInterval(() => {
      fetchData(true)
    }, 5000)
  } else if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function fetchData(silent = false) {
  if (!props.device?.id) return
  if (!silent) loading.value = true
  try {
    const res = await getDeviceSnmpInterfaces(props.device.id)
    interfaces.value = res.interfaces || []
    lastUpdated.value = new Date().toLocaleTimeString()

    // Update history for charts
    const nowTime = new Date().toLocaleTimeString()
    interfaces.value.forEach(port => {
      if (!trafficHistory[port.if_index]) {
        trafficHistory[port.if_index] = { time: [], in: [], out: [] }
      }
      const history = trafficHistory[port.if_index]
      history.time.push(nowTime)
      history.in.push((port.in_rate_bps / 1000 / 1000).toFixed(2)) // Mbps
      history.out.push((port.out_rate_bps / 1000 / 1000).toFixed(2)) // Mbps
      if (history.time.length > 20) {
        history.time.shift()
        history.in.shift()
        history.out.shift()
      }
    })

    if (!selectedPort.value && interfaces.value.length > 0) {
      selectedPort.value = interfaces.value[0]
    } else if (selectedPort.value) {
      // Refresh selected port reference
      const updated = interfaces.value.find(i => i.if_index === selectedPort.value.if_index)
      if (updated) selectedPort.value = updated
    }

    nextTick(() => {
      renderChart()
    })
  } catch (err) {
    if (!silent) {
      ElMessage.error(err.response?.data?.detail || '获取 SNMP 接口失败')
    }
  } finally {
    if (!silent) loading.value = false
  }
}

function handleSelectPort(port) {
  selectedPort.value = port
  nextTick(() => {
    renderChart()
  })
}

function renderChart() {
  if (!chartRef.value || !selectedPort.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const history = trafficHistory[selectedPort.value.if_index] || { time: [], in: [], out: [] }

  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['入向 (Mbps)', '出向 (Mbps)']
    },
    grid: {
      top: 30,
      left: 50,
      right: 20,
      bottom: 25
    },
    xAxis: {
      type: 'category',
      data: history.time,
      boundaryGap: false
    },
    yAxis: {
      type: 'value',
      name: 'Mbps'
    },
    series: [
      {
        name: '入向 (Mbps)',
        type: 'line',
        smooth: true,
        data: history.in,
        itemStyle: { color: '#38a169' }
      },
      {
        name: '出向 (Mbps)',
        type: 'line',
        smooth: true,
        data: history.out,
        itemStyle: { color: '#3182ce' }
      }
    ]
  }

  chartInstance.setOption(option)
}

function onClose() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  autoRefresh.value = false
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

onBeforeUnmount(() => {
  onClose()
})
</script>

<style scoped>
.snmp-container {
  min-height: 350px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.right-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chart-section {
  background: #f7fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 14px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.chart-header h4 {
  margin: 0;
  color: #2d3748;
}

.chart-rates {
  font-size: 13px;
  font-weight: bold;
}

.rate-in {
  color: #2f855a;
  margin-right: 12px;
}

.rate-out {
  color: #2b6cb0;
}

.echarts-box {
  width: 100%;
  height: 180px;
}

.table-section {
  margin-top: 10px;
}
</style>
