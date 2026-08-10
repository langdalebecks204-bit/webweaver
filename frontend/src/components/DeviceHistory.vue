<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { fetchDeviceHistory } from '../api/devices'

const props = defineProps({ device: { type: Object, required: true } })
const emit = defineEmits(['close'])

const granularity = ref('hour')
const days = ref(7)
const chartEl = ref(null)
const records = ref([])
let chart = null

const chartOptions = computed(() => buildOptions(records.value, granularity.value))

function buildOptions(recs, gran) {
  const buckets = new Map()
  const keyOf = gran === 'day'
    ? (t) => `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
    : (t) => {
        const d = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
        return `${d} ${String(t.getHours()).padStart(2, '0')}:00`
      }
  for (const rec of recs) {
    if (rec.latency_ms == null) continue
    const key = keyOf(new Date(rec.checked_at))
    const b = buckets.get(key) || { sum: 0, count: 0 }
    b.sum += rec.latency_ms
    b.count += 1
    buckets.set(key, b)
  }
  const keys = [...buckets.keys()].sort()
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: keys, axisLabel: { rotate: 40 } },
    yAxis: { type: 'value', name: '平均延时(ms)' },
    series: [
      {
        type: 'bar',
        data: keys.map((k) => Math.round(buckets.get(k).sum / buckets.get(k).count)),
      },
    ],
  }
}

async function load() {
  const { data } = await fetchDeviceHistory(props.device.id, days.value)
  records.value = data.records
}

function renderChart() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(chartOptions.value, true)
}

function onResize() {
  if (chart) chart.resize()
}

watch(days, load)
watch(chartOptions, renderChart)

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<template>
  <el-dialog
    :model-value="true"
    :title="`历史延时 - ${props.device.name}`"
    width="720px"
    @close="emit('close')"
  >
    <div class="controls">
      <el-radio-group v-model="granularity">
        <el-radio-button value="hour">按小时</el-radio-button>
        <el-radio-button value="day">按天</el-radio-button>
      </el-radio-group>
      <el-select v-model="days" style="width: 120px">
        <el-option label="最近 1 天" :value="1" />
        <el-option label="最近 7 天" :value="7" />
        <el-option label="最近 30 天" :value="30" />
      </el-select>
    </div>
    <div ref="chartEl" class="chart" />
  </el-dialog>
</template>

<style scoped>
.controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}
.chart {
  width: 100%;
  height: 380px;
}
</style>
