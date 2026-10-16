<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAssetsStore } from '../stores/assets'
import { useDevicesStore } from '../stores/devices'
import { useAuthStore } from '../stores/auth'
import { flattenTree } from '../stores/devicesHelpers'
import { allTypeOptions, typeLabel } from '../utils/deviceTypes'
import { useSettingsStore } from '../stores/settings'

const assets = useAssetsStore()
const devices = useDevicesStore()
const auth = useAuthStore()
const settings = useSettingsStore()

const isAdmin = computed(() => auth.user?.role === 'admin')
const typeOptions = computed(() => allTypeOptions(settings.builtinTypes, settings.customTypes))

const keyword = ref('')
const managedFilter = ref('') // '' | 'managed' | 'unmanaged'

// Switches and routers that can collect ARP
const collectors = computed(() => {
  const flat = flattenTree(devices.tree)
  return flat.filter((d) => ['switch', 'router', 'gateway'].includes(d.type))
})

// Flat candidate parents for enrollment
const parentCandidates = computed(() => {
  return flattenTree(devices.tree)
})

const filteredAssets = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return assets.items.filter((item) => {
    if (managedFilter.value === 'managed' && !item.is_managed) return false
    if (managedFilter.value === 'unmanaged' && item.is_managed) return false

    if (!kw) return true
    const matchIp = (item.ip || '').toLowerCase().includes(kw)
    const matchMac = (item.mac || '').toLowerCase().includes(kw)
    const matchVendor = (item.vendor || '').toLowerCase().includes(kw)
    const matchDevName = (item.managed_device_name || '').toLowerCase().includes(kw)
    const matchIfName = (item.if_name || '').toLowerCase().includes(kw)
    return matchIp || matchMac || matchVendor || matchDevName || matchIfName
  })
})

// Vendor tag color mapping
function getVendorTagType(vendor) {
  if (!vendor) return 'info'
  const v = vendor.toLowerCase()
  if (v.includes('huawei') || v.includes('cisco')) return 'danger'
  if (v.includes('h3c') || v.includes('ruijie')) return 'primary'
  if (v.includes('tp-link') || v.includes('apple')) return 'success'
  if (v.includes('hikvision') || v.includes('dahua')) return 'warning'
  return 'info'
}

function copyText(text) {
  if (!text) return
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.info(text)
  })
}

// Enrollment Dialog State
const enrollDialogVisible = ref(false)
const enrolling = ref(false)
const enrollForm = ref({
  name: '',
  type: 'server',
  ip_address: '',
  mac_address: '',
  parent_id: null,
  location: '',
})

function guessTypeByVendor(vendor) {
  if (!vendor) return 'server'
  const v = vendor.toLowerCase()
  if (v.includes('hikvision') || v.includes('dahua') || v.includes('uniview')) return 'camera'
  if (v.includes('huawei') || v.includes('h3c') || v.includes('cisco') || v.includes('ruijie')) return 'switch'
  if (v.includes('tp-link')) return 'ap'
  return 'server'
}

function openEnrollDialog(item) {
  const guessedType = guessTypeByVendor(item.vendor)
  const defaultName = item.vendor && item.vendor !== '未知厂商' 
    ? `${item.vendor}-${item.ip.split('.').slice(-2).join('.')}`
    : `Device-${item.ip.split('.').slice(-2).join('.')}`

  enrollForm.value = {
    name: defaultName,
    type: guessedType,
    ip_address: item.ip,
    mac_address: item.mac,
    parent_id: item.collector_device_id || null,
    location: '',
  }
  enrollDialogVisible.value = true
}

async function onConfirmEnroll() {
  if (!enrollForm.value.name.trim()) {
    ElMessage.warning('请输入设备名称')
    return
  }
  enrolling.value = true
  try {
    await assets.enroll({
      name: enrollForm.value.name.trim(),
      type: enrollForm.value.type,
      ip_address: enrollForm.value.ip_address || null,
      mac_address: enrollForm.value.mac_address || null,
      parent_id: enrollForm.value.parent_id,
      location: enrollForm.value.location || null,
    })
    await devices.load()
    ElMessage.success('设备纳管成功')
    enrollDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '纳管失败')
  } finally {
    enrolling.value = false
  }
}

async function onScan() {
  try {
    await assets.scan()
    ElMessage.success('扫描完成')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '扫描失败')
  }
}

function exportCsv() {
  const rows = filteredAssets.value
  if (!rows.length) {
    ElMessage.warning('暂无数据可导出')
    return
  }
  const headers = ['IP地址', 'MAC地址', '硬件厂商', '学习端口', '采集源', '纳管状态', '对应设备名', '设备类型']
  const csvContent = [
    headers.join(','),
    ...rows.map((r) => [
      r.ip,
      r.mac,
      `"${r.vendor || ''}"`,
      `"${r.if_name || ''}"`,
      `"${r.collector_device_name || ''}"`,
      r.is_managed ? '已纳管' : '未纳管',
      `"${r.managed_device_name || ''}"`,
      `"${r.managed_device_type || ''}"`,
    ].join(',')),
  ].join('\n')

  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `IP_MAC资产台账_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  assets.load()
})
</script>

<template>
  <div class="assets-panel">
    <!-- Stat Cards Overview -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">全网活跃 IP / MAC</div>
        <div class="stat-value total">{{ assets.totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已纳管设备</div>
        <div class="stat-value managed">{{ assets.managedCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">未登记终端（待纳管）</div>
        <div class="stat-value unmanaged">{{ assets.unmanagedCount }}</div>
      </div>
      <div class="stat-card vendors-card">
        <div class="stat-label">主要硬件厂商</div>
        <div class="vendor-tags">
          <el-tag
            v-for="v in assets.vendorStats.slice(0, 5)"
            :key="v.name"
            size="small"
            :type="getVendorTagType(v.name)"
            class="vendor-tag"
          >
            {{ v.name }}: {{ v.count }}
          </el-tag>
          <span v-if="!assets.vendorStats.length" class="empty-hint">暂无统计</span>
        </div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="filters">
        <el-select
          v-model="assets.selectedCollectorId"
          placeholder="全部采集源"
          clearable
          style="width: 170px"
          @change="assets.load()"
        >
          <el-option label="全网与宿主机扫描" :value="null" />
          <el-option
            v-for="c in collectors"
            :key="c.id"
            :label="`${c.name} (${c.ip_address || '无IP'})`"
            :value="c.id"
          />
        </el-select>

        <el-input
          v-model="keyword"
          placeholder="搜索 IP / MAC / 厂商 / 端口 / 设备名"
          clearable
          style="width: 260px"
        />

        <el-select v-model="managedFilter" clearable placeholder="全部状态" style="width: 120px">
          <el-option label="全部状态" value="" />
          <el-option label="仅未纳管" value="unmanaged" />
          <el-option label="仅已纳管" value="managed" />
        </el-select>
      </div>

      <div class="actions">
        <el-button v-if="isAdmin" type="primary" :loading="assets.scanning" @click="onScan">
          扫描 ARP
        </el-button>
        <el-button :loading="assets.loading" @click="assets.load()">刷新</el-button>
        <el-button @click="exportCsv">导出 CSV</el-button>
      </div>
    </div>

    <!-- Asset Table -->
    <el-table
      v-loading="assets.loading || assets.scanning"
      :data="filteredAssets"
      size="small"
      stripe
      class="asset-table"
    >
      <el-table-column prop="ip" label="IP 地址" min-width="140">
        <template #default="{ row }">
          <span class="mono ip-link" @click="copyText(row.ip)">{{ row.ip }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="mac" label="MAC 地址" min-width="155">
        <template #default="{ row }">
          <span class="mono mac-link" @click="copyText(row.mac)">{{ row.mac }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="vendor" label="硬件厂商" min-width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="getVendorTagType(row.vendor)">
            {{ row.vendor || '未知厂商' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="if_name" label="学习端口" min-width="130">
        <template #default="{ row }">
          <span>{{ row.if_name || '-' }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="collector_device_name" label="采集设备" min-width="120">
        <template #default="{ row }">
          <span>{{ row.collector_device_name || '-' }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="is_managed" label="纳管状态" width="130">
        <template #default="{ row }">
          <el-tag v-if="row.is_managed" type="success" size="small">已纳管</el-tag>
          <el-tag v-else type="warning" size="small" effect="plain">未登记终端</el-tag>
        </template>
      </el-table-column>

      <el-table-column label="关联系统设备" min-width="160">
        <template #default="{ row }">
          <div v-if="row.is_managed" class="managed-info">
            <span class="dev-name">{{ row.managed_device_name }}</span>
            <el-tag size="small" type="info" class="dev-type">{{ typeLabel(row.managed_device_type) }}</el-tag>
          </div>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>

      <el-table-column v-if="isAdmin" label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="!row.is_managed"
            type="primary"
            size="small"
            plain
            @click="openEnrollDialog(row)"
          >
            一键纳管
          </el-button>
          <span v-else class="text-muted text-sm">已入库</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- Enroll Dialog -->
    <el-dialog
      v-model="enrollDialogVisible"
      title="一键纳管终端设备"
      width="480px"
      destroy-on-close
    >
      <el-form label-width="90px">
        <el-form-item label="设备名称" required>
          <el-input v-model="enrollForm.name" placeholder="如: 二楼会议室摄像头" />
        </el-form-item>

        <el-form-item label="设备类型" required>
          <el-select v-model="enrollForm.type" style="width: 100%">
            <el-option
              v-for="opt in typeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="IP 地址">
          <el-input v-model="enrollForm.ip_address" disabled />
        </el-form-item>

        <el-form-item label="MAC 地址">
          <el-input v-model="enrollForm.mac_address" disabled />
        </el-form-item>

        <el-form-item label="所属节点">
          <el-select
            v-model="enrollForm.parent_id"
            placeholder="根节点（无父级）"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="p in parentCandidates"
              :key="p.id"
              :label="`${p.name} (${typeLabel(p.type)})`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="安装位置">
          <el-input v-model="enrollForm.location" placeholder="如: 机房A区、前台大厅" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="enrollDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="enrolling" @click="onConfirmEnroll">
          确认纳管
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.assets-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.stat-card {
  background: var(--el-bg-color-overlay, #ffffff);
  border: 1px solid var(--el-border-color-light, #ebeef5);
  border-radius: 8px;
  padding: 14px 18px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-value.total {
  color: var(--el-color-primary, #409eff);
}

.stat-value.managed {
  color: var(--el-color-success, #67c23a);
}

.stat-value.unmanaged {
  color: var(--el-color-warning, #e6a23c);
}

.vendors-card {
  grid-column: span 1;
}

.vendor-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.vendor-tag {
  font-size: 12px;
}

.empty-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.actions {
  display: flex;
  gap: 8px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}

.ip-link, .mac-link {
  cursor: pointer;
}
.ip-link:hover, .mac-link:hover {
  color: var(--el-color-primary);
  text-decoration: underline;
}

.managed-info {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dev-name {
  font-weight: 500;
}

.dev-type {
  font-size: 11px;
}

.text-muted {
  color: var(--el-text-color-placeholder);
}

.text-sm {
  font-size: 12px;
}

.asset-table {
  width: 100%;
}
</style>
