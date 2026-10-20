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

const activeTab = ref('backbone')
const loading = ref(false)
const applying = ref(false)
const updateHierarchy = ref(true)

// Backbone (LLDP) State
const scanResult = ref({
  links: [],
  unmatched_neighbors: [],
  scanned_devices_count: 0,
})
const selectedLinks = ref([])

// Edge (FDB) State
const edgeLoading = ref(false)
const edgeResult = ref({
  direct_terminals: [],
  unmanaged_hubs: [],
  ap_clusters: [],
})
const selectedDirect = ref([])
const hubSelections = ref([])

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

async function loadEdgeDiscovery() {
  edgeLoading.value = true
  try {
    const res = await topologyApi.edgeDiscover()
    const data = res.data || { direct_terminals: [], unmanaged_hubs: [], ap_clusters: [] }
    edgeResult.value = data
    selectedDirect.value = data.direct_terminals.filter((dt) => dt.device_id)
    hubSelections.value = data.unmanaged_hubs.map((hub) => ({
      ...hub,
      checked: true,
      customName: hub.suggested_name,
    }))
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '边缘 FDB 探测失败')
  } finally {
    edgeLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      if (activeTab.value === 'backbone') {
        loadDiscovery()
      } else {
        loadEdgeDiscovery()
      }
    }
  },
  { immediate: true }
)

function onTabChange(tab) {
  if (tab === 'edge' && !edgeResult.value.direct_terminals.length && !edgeResult.value.unmanaged_hubs.length) {
    loadEdgeDiscovery()
  } else if (tab === 'backbone' && !scanResult.value.links.length) {
    loadDiscovery()
  }
}

function handleLinkSelectionChange(val) {
  selectedLinks.value = val
}

function handleDirectSelectionChange(val) {
  selectedDirect.value = val
}

async function onApplyBackbone() {
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

async function onApplyEdge() {
  const chosenHubs = hubSelections.value.filter((h) => h.checked)
  if (!selectedDirect.value.length && !chosenHubs.length) {
    ElMessage.warning('请至少选择一项直连终端或分线交换机')
    return
  }
  applying.value = true
  try {
    const hubsToCreate = chosenHubs.map((h) => ({
      name: h.customName || h.suggested_name,
      switch_id: h.switch_id,
      port_num: h.port_num,
      port_name: h.port_name,
      device_ids: h.attached_devices.map((d) => d.device_id),
      unregistered_macs: h.unregistered_assets.map((a) => a.mac),
    }))

    const payload = {
      direct_terminals: selectedDirect.value,
      hubs_to_create: hubsToCreate,
    }

    const res = await topologyApi.applyEdge(payload)
    ElMessage.success(
      `成功应用边缘接入：直连终端 ${res.data.applied_direct_count} 台，聚合生成分线器 ${res.data.created_hubs_count} 台！`
    )
    await store.load()
    emit('applied')
    emit('update:modelValue', false)
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '边缘拓扑应用失败')
  } finally {
    applying.value = false
  }
}

function onOpen() {
  if (activeTab.value === 'backbone') {
    loadDiscovery()
  } else {
    loadEdgeDiscovery()
  }
}
</script>

<template>
  <el-dialog
    :model-value="props.modelValue"
    title="⚡ 自动化物理拓扑与接入探测向导"
    width="840px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <el-tabs v-model="activeTab" type="card" @tab-change="onTabChange">
      <!-- Tab 1: 交换机骨干互联 -->
      <el-tab-pane label="交换机骨干互联 (LLDP/Bridge)" name="backbone">
        <div v-loading="loading" class="tab-pane-content">
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
              max-height="320"
              @selection-change="handleLinkSelectionChange"
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
      </el-tab-pane>

      <!-- Tab 2: 边缘终端与分线器推导 -->
      <el-tab-pane label="边缘终端与分线器推导 (CAM/FDB)" name="edge">
        <div v-loading="edgeLoading" class="tab-pane-content">
          <!-- Stats row -->
          <div class="stats-row">
            <div class="stat-badge highlight">
              <span class="label">直连有线终端：</span>
              <span class="val">{{ edgeResult.direct_terminals.length }} 台</span>
            </div>
            <div class="stat-badge warning">
              <span class="label">建议聚合分线器：</span>
              <span class="val">{{ edgeResult.unmanaged_hubs.length }} 个</span>
            </div>
            <div class="stat-badge">
              <span class="label">收敛无线 AP：</span>
              <span class="val">{{ edgeResult.ap_clusters.length }} 处</span>
            </div>
          </div>

          <!-- Part 1: Direct Terminals -->
          <div class="section-block">
            <div class="section-title">
              <span>📌 单 MAC 精准直连端口 ({{ edgeResult.direct_terminals.length }})</span>
              <span class="section-hint">单端口仅学习到 1 个固定 MAC，建议直接挂载至对应物理口</span>
            </div>
            <div class="table-wrap">
              <el-table
                :data="edgeResult.direct_terminals"
                size="small"
                stripe
                max-height="200"
                @selection-change="handleDirectSelectionChange"
              >
                <el-table-column type="selection" width="45" />
                <el-table-column label="交换机 & 端口" min-width="160">
                  <template #default="scope">
                    <span class="dev-name">{{ scope?.row?.switch_name }}</span>
                    <el-tag size="small" type="info" class="port-tag">{{ scope?.row?.port_name }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="直连设备名称" min-width="140">
                  <template #default="scope">
                    <b>{{ scope?.row?.device_name }}</b>
                  </template>
                </el-table-column>
                <el-table-column label="IP / MAC 地址" min-width="180">
                  <template #default="scope">
                    <div>{{ scope?.row?.ip_address || '-' }}</div>
                    <div class="text-secondary">{{ scope?.row?.mac }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="设备厂商" width="110">
                  <template #default="scope">
                    <el-tag size="small">{{ scope?.row?.vendor || '-' }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>

          <!-- Part 2: Unmanaged Hubs -->
          <div class="section-block">
            <div class="section-title">
              <span>🔌 非网管傻瓜交换机推断与聚合 ({{ edgeResult.unmanaged_hubs.length }})</span>
              <span class="section-hint">端口学习到多个有线 MAC，建议聚合为虚拟分线节点，防止线条混乱</span>
            </div>

            <div v-if="!hubSelections.length" class="empty-hint">暂未检测到多有线 MAC 聚集端口</div>

            <div v-else class="hubs-list">
              <div
                v-for="(hub, idx) in hubSelections"
                :key="idx"
                class="hub-card"
              >
                <div class="hub-header">
                  <el-checkbox v-model="hub.checked" />
                  <span class="hub-location">【{{ hub.switch_name }}】{{ hub.port_name }}：</span>
                  <el-input
                    v-model="hub.customName"
                    size="small"
                    style="width: 260px"
                    placeholder="输入分线交换机名称"
                  />
                  <el-tag size="small" type="warning" style="margin-left: 8px">
                    挂载 {{ hub.terminal_count }} 台设备
                  </el-tag>
                </div>

                <div class="hub-terminals">
                  <span
                    v-for="(dev, dIdx) in hub.attached_devices"
                    :key="dIdx"
                    class="terminal-chip"
                  >
                    💻 {{ dev.name }} ({{ dev.ip || dev.mac }})
                  </span>
                  <span
                    v-for="(unreg, uIdx) in hub.unregistered_assets"
                    :key="'u-' + uIdx"
                    class="terminal-chip unreg"
                  >
                    ➕ 未登记: {{ unreg.vendor }} ({{ unreg.mac }})
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Part 3: AP Clusters Notice -->
          <div v-if="edgeResult.ap_clusters.length" class="section-block ap-block">
            <div class="section-title">
              <span>📶 无线 AP 漫游终端已智能收敛 ({{ edgeResult.ap_clusters.length }})</span>
            </div>
            <div
              v-for="(ap, aIdx) in edgeResult.ap_clusters"
              :key="aIdx"
              class="ap-row"
            >
              <span>【{{ ap.switch_name }}】的 <b>{{ ap.port_name }}</b> 检测到无线 AP 覆盖区：</span>
              <span class="text-secondary">
                关联 AP: {{ ap.ap_name }}，已识别并过滤 {{ ap.mobile_count }} 台手机/便携终端噪点
              </span>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <div class="dialog-footer">
        <el-button
          :loading="loading || edgeLoading"
          @click="activeTab === 'backbone' ? loadDiscovery() : loadEdgeDiscovery()"
        >
          重新探测
        </el-button>
        <el-button @click="emit('update:modelValue', false)">取消</el-button>

        <el-button
          v-if="activeTab === 'backbone'"
          type="primary"
          :loading="applying"
          :disabled="!selectedLinks.length"
          @click="onApplyBackbone"
        >
          一键固化应用骨干链路 ({{ selectedLinks.length }})
        </el-button>

        <el-button
          v-else
          type="primary"
          :loading="applying"
          @click="onApplyEdge"
        >
          一键应用边缘接入 (直连: {{ selectedDirect.length }}, 分线器: {{ hubSelections.filter(h => h.checked).length }})
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.tab-pane-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 6px;
}

.stats-row {
  display: flex;
  gap: 16px;
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

.section-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.section-hint {
  font-weight: normal;
  font-size: 12px;
  color: var(--el-text-color-secondary);
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

.hubs-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hub-card {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  background: var(--el-fill-color-blank, #fff);
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hub-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hub-location {
  font-weight: 500;
  font-size: 13px;
}

.hub-terminals {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-left: 24px;
}

.terminal-chip {
  background: var(--el-fill-color-light, #f5f7fa);
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.terminal-chip.unreg {
  border-style: dashed;
  color: var(--el-color-warning-dark-2);
}

.ap-block {
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 6px;
  padding: 10px 14px;
}

.ap-row {
  font-size: 12px;
  color: #b88230;
}

.empty-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  padding: 10px 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
