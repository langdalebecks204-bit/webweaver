<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import topologyApi from '../api/topology'
import { useDevicesStore } from '../stores/devices'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'applied'])

const store = useDevicesStore()

const loading = ref(false)
const applying = ref(false)
const updateHierarchy = ref(true)

const scanResult = ref({
  links: [],
  unmatched_neighbors: [],
  scanned_devices_count: 0,
})

const selectedLinks = ref([])

async function loadDiscovery() {
  loading.value = true
  try {
    const res = await topologyApi.getLldpNeighbors()
    scanResult.value = res.data || { links: [], unmatched_neighbors: [], scanned_devices_count: 0 }
    selectedLinks.value = [...scanResult.value.links]
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || 'LLDP 探测失败，请检查交换机 SNMP 配置与网络连通性')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      loadDiscovery()
    }
  },
  { immediate: true }
)

function handleSelectionChange(val) {
  selectedLinks.value = val
}

async function onApply() {
  if (!selectedLinks.value.length) {
    ElMessage.warning('请至少选择一条互联链路')
    return
  }
  applying.value = true
  try {
    const res = await topologyApi.applyLldp(selectedLinks.value, updateHierarchy.value)
    ElMessage.success(`成功固化 ${res.data.applied_count} 个物理端口互联！`)
    await store.load()
    emit('applied')
    emit('update:modelValue', false)
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '应用失败')
  } finally {
    applying.value = false
  }
}

function onOpen() {
  loadDiscovery()
}
</script>

<template>
  <el-dialog
    :model-value="props.modelValue"
    title="LLDP 自动化物理拓扑与端口对探测"
    width="780px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <div v-loading="loading" class="lldp-modal-content">
      <!-- Overview stats -->
      <div class="stats-row">
        <div class="stat-badge">
          <span class="label">扫描交换机：</span>
          <span class="val">{{ scanResult.scanned_devices_count }} 台</span>
        </div>
        <div class="stat-badge highlight">
          <span class="label">发现物理互联：</span>
          <span class="val">{{ scanResult.links.length }} 条链路</span>
        </div>
        <div class="stat-badge warning">
          <span class="label">未识别邻居：</span>
          <span class="val">{{ scanResult.unmatched_neighbors.length }} 个</span>
        </div>
      </div>

      <!-- Links table -->
      <div class="table-wrap">
        <el-table
          :data="scanResult.links"
          size="small"
          stripe
          max-height="300"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="45" />

          <el-table-column label="本端设备 & 端口" min-width="170">
            <template #default="scope">
              <span class="dev-name">{{ scope?.row?.source_name }}</span>
              <el-tag size="small" type="info" class="port-tag">{{ scope?.row?.source_port }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column label="连接" width="60" align="center">
            <template #default>
              <span class="link-arrow">⟷</span>
            </template>
          </el-table-column>

          <el-table-column label="对端设备 & 端口" min-width="170">
            <template #default="scope">
              <span class="dev-name">{{ scope?.row?.target_name }}</span>
              <el-tag size="small" type="info" class="port-tag">{{ scope?.row?.target_port }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column label="探测确认" width="110" align="center">
            <template #default="scope">
              <el-tag v-if="scope?.row?.is_bidirectional" size="small" type="success">双向确认</el-tag>
              <el-tag v-else size="small" type="primary">单向探测</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Unmatched Neighbors (if any) -->
      <el-collapse v-if="scanResult.unmatched_neighbors.length" class="unmatched-collapse">
        <el-collapse-item title="发现未在平台登记的外部对端交换机/设备">
          <div
            v-for="(un, idx) in scanResult.unmatched_neighbors"
            :key="idx"
            class="unmatched-item"
          >
            <span>【{{ un.collector_device_name }}】的 <b>{{ un.local_port }}</b> 连向外部设备：</span>
            <span class="text-secondary">
              SysName: {{ un.remote_sys_name || '-' }}, MAC: {{ un.remote_chassis_id || '-' }}, IP: {{ un.remote_man_ip || '-' }}
            </span>
          </div>
        </el-collapse-item>
      </el-collapse>

      <div class="options-row">
        <el-checkbox v-model="updateHierarchy">
          自动优化层级结构（将级联接入交换机作为子节点挂载到上级）
        </el-checkbox>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button :loading="loading" @click="loadDiscovery">重新探测</el-button>
        <el-button @click="emit('update:modelValue', false)">取消</el-button>
        <el-button
          type="primary"
          :loading="applying"
          :disabled="!selectedLinks.length"
          @click="onApply"
        >
          一键固化应用到拓扑 ({{ selectedLinks.length }})
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.lldp-modal-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.stats-row {
  display: flex;
  gap: 12px;
  background: var(--el-fill-color-light, #f5f7fa);
  padding: 10px 14px;
  border-radius: 6px;
}

.stat-badge {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.stat-badge .val {
  font-weight: 600;
}
.stat-badge.highlight .val {
  color: var(--el-color-primary, #409eff);
}
.stat-badge.warning .val {
  color: var(--el-color-warning, #e6a23c);
}

.table-wrap {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 6px;
  overflow: hidden;
}

.dev-name {
  font-weight: 500;
  margin-right: 6px;
}

.port-tag {
  font-family: monospace;
  font-size: 11px;
}

.link-arrow {
  color: var(--el-color-primary);
  font-weight: bold;
}

.unmatched-collapse {
  margin-top: 4px;
}

.unmatched-item {
  font-size: 12px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--el-border-color-extra-light, #f2f6fc);
}

.text-secondary {
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

.options-row {
  padding: 4px 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
