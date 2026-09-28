<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  portCount: { type: Number, default: 0 },
  bindings: { type: Object, default: () => ({}) },
  childDevices: { type: Array, default: () => [] },
  parentDevices: { type: Array, default: () => [] },
  parentDevice: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'save'])

const rows = ref([])

const uplinkCandidates = computed(() => {
  if (props.parentDevices && props.parentDevices.length > 0) {
    return props.parentDevices
  }
  if (props.parentDevice) {
    return [{ ...props.parentDevice, isParent: true }]
  }
  return props.childDevices
})

const downlinkCandidates = computed(() => {
  return props.childDevices
})

watch(
  () => [props.portCount, props.modelValue],
  () => {
    if (!props.modelValue) return
    rows.value = Array.from({ length: props.portCount }, (_, i) => {
      const port = String(i + 1)
      const existing = props.bindings[port]
      return {
        port,
        target_id: existing ? existing.target_id : null,
        type: existing ? existing.type : 'downlink',
      }
    })
  },
  { immediate: true }
)

function onTypeChange(row) {
  if (row.type === 'uplink') {
    if (!row.target_id) {
      const parent = uplinkCandidates.value.find((d) => d.isParent) || uplinkCandidates.value[0]
      if (parent) {
        row.target_id = parent.id
      }
    }
  } else if (row.type === 'downlink') {
    const wasParent = uplinkCandidates.value.some((d) => d.id === row.target_id && d.isParent)
    if (wasParent) {
      row.target_id = null
    }
  }
}

function onClose() {
  emit('update:modelValue', false)
}

function onSave() {
  const result = {}
  for (const row of rows.value) {
    if (row.target_id !== null && row.target_id !== undefined && row.target_id !== '') {
      result[row.port] = {
        target_id: row.target_id,
        type: row.type || 'downlink',
      }
    }
  }
  emit('save', result)
  onClose()
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="端口绑定配置" width="540px" @close="onClose">
    <div v-for="row in rows" :key="row.port" class="port-row">
      <span class="port-num">Port {{ row.port }}</span>
      <el-select
        v-model="row.target_id"
        :placeholder="row.type === 'uplink' ? '选择上级/上联设备' : '绑定下联设备'"
        clearable
        class="bind-select"
      >
        <el-option
          v-for="d in (row.type === 'uplink' ? uplinkCandidates : downlinkCandidates)"
          :key="d.id"
          :label="d.isParent ? `${d.name} (上级设备)` : d.name"
          :value="d.id"
        />
      </el-select>
      <el-select v-model="row.type" class="type-select" @change="onTypeChange(row)">
        <el-option label="下联" value="downlink" />
        <el-option label="上联" value="uplink" />
      </el-select>
    </div>
    <template #footer>
      <el-button @click="onClose">取消</el-button>
      <el-button type="primary" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.port-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.port-num {
  width: 58px;
  color: #606266;
  font-weight: 500;
}
.bind-select {
  flex: 1;
}
.type-select {
  width: 100px;
}
</style>
