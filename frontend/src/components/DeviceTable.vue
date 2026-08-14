<script setup>
import { computed, ref } from 'vue'
import { useDevicesStore } from '../stores/devices'
import { useAuthStore } from '../stores/auth'
import { filterDevices, flattenTree } from '../stores/devicesHelpers'
import { ElMessage, ElMessageBox } from 'element-plus'
import { typeLabel } from '../utils/deviceTypes'
import { downloadCsv, toCsv } from '../utils/csv'

const store = useDevicesStore()
const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const keyword = ref('')
const statusFilter = ref('')

const props = defineProps({ onEdit: Function })

const flatDevices = computed(() => flattenTree(store.tree))

const filteredDevices = computed(() =>
  filterDevices(flatDevices.value, { keyword: keyword.value, status: statusFilter.value })
)

function statusText(s) {
  return s === 'online' ? '在线' : s === 'offline' ? '离线' : s === 'warning' ? '警告' : '未知'
}

function statusType(s) {
  if (s === 'online') return 'success'
  if (s === 'offline') return 'danger'
  if (s === 'warning') return 'warning'
  return 'info'
}

async function onRemove(d) {
  try {
    await ElMessageBox.confirm(`确定删除"${d.name}"及其全部子节点？`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await store.remove(d.id)
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

async function onRecheck(d) {
  try {
    await store.recheck(d.id)
    ElMessage.success('已巡检')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '巡检失败')
  }
}

const csvColumns = [
  { key: 'name', header: '名称' },
  { key: 'type', header: '类型', format: typeLabel },
  { key: 'parentName', header: '所属分组', format: (v) => v || '' },
  { key: 'ip_address', header: 'IP', format: (v) => v || '' },
  { key: 'port', header: '端口', format: (v) => (v ?? '') },
  { key: 'location', header: '位置', format: (v) => v || '' },
  { key: 'status', header: '状态', format: statusText },
  { key: 'latency_ms', header: '延时', format: (v) => (v != null ? `${v} ms` : '') },
  { key: 'last_check', header: '最近巡检', format: (v) => (v ? new Date(v).toLocaleString() : '') },
]

function onExport() {
  const rows = filteredDevices.value
  if (!rows.length) {
    ElMessage.warning('无数据可导出')
    return
  }
  const csv = toCsv(rows, csvColumns)
  downloadCsv(`设备资产_${new Date().toISOString().slice(0, 10)}.csv`, csv)
  ElMessage.success(`已导出 ${rows.length} 条记录`)
}
</script>

<template>
  <div>
    <div class="filters">
      <el-input
        v-model="keyword"
        placeholder="搜索名称 / IP / 位置"
        clearable
        class="search"
      />
      <el-select v-model="statusFilter" clearable placeholder="全部状态" class="status">
        <el-option label="在线" value="online" />
        <el-option label="警告" value="warning" />
        <el-option label="离线" value="offline" />
        <el-option label="未知" value="unknown" />
      </el-select>
      <el-button size="small" @click="onExport">导出 CSV</el-button>
    </div>
    <el-table :data="filteredDevices" size="small">
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="type" label="类型" width="80">
        <template #default="{ row }">{{ typeLabel(row.type) }}</template>
      </el-table-column>
      <el-table-column prop="parentName" label="所属分组" min-width="120">
        <template #default="{ row }">{{ row.parentName || '-' }}</template>
      </el-table-column>
      <el-table-column prop="ip_address" label="IP" width="140">
        <template #default="{ row }">{{ row.ip_address || '-' }}</template>
      </el-table-column>
      <el-table-column prop="port" label="端口" width="80">
        <template #default="{ row }">{{ row.port ?? '-' }}</template>
      </el-table-column>
      <el-table-column prop="location" label="位置" min-width="120">
        <template #default="{ row }">{{ row.location || '-' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="latency_ms" label="延时" width="90">
        <template #default="{ row }">{{ row.latency_ms != null ? row.latency_ms + ' ms' : '-' }}</template>
      </el-table-column>
      <el-table-column prop="last_check" label="最近巡检" min-width="150">
        <template #default="{ row }">
          {{ row.last_check ? new Date(row.last_check).toLocaleString() : '-' }}
        </template>
      </el-table-column>
      <el-table-column v-if="isAdmin" label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" @click="props.onEdit?.(row)">编辑</el-button>
          <el-button size="small" @click="onRecheck(row)">巡检</el-button>
          <el-button size="small" type="danger" @click="onRemove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.search {
  width: 240px;
}
.status {
  width: 120px;
}
</style>