<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  portCount: { type: Number, default: 0 },
  bindings: { type: Object, default: () => ({}) },
  childDevices: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'save'])

const rows = ref([])

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

function onClose() {
  emit('update:modelValue', false)
}

function onSave() {
  const result = {}
  for (const row of rows.value) {
    if (row.target_id) {
      result[row.port] = { target_id: row.target_id, type: row.type }
    }
  }
  emit('save', result)
  onClose()
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="端口绑定配置" width="520px" @close="onClose">
    <div v-for="row in rows" :key="row.port" class="port-row">
      <span class="port-num">Port {{ row.port }}</span>
      <el-select v-model="row.target_id" placeholder="绑定设备" clearable class="bind-select">
        <el-option v-for="d in childDevices" :key="d.id" :label="d.name" :value="d.id" />
      </el-select>
      <el-select v-model="row.type" class="type-select">
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
  width: 60px;
  color: #606266;
}
.bind-select {
  flex: 1;
}
.type-select {
  width: 100px;
}
</style>
