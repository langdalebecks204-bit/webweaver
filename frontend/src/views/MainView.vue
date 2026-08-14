<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { useDevicesStore } from '../stores/devices'
import { useSettingsStore } from '../stores/settings'
import { useExternalStore } from '../stores/external'
import DeviceTree from '../components/DeviceTree.vue'
import DeviceTable from '../components/DeviceTable.vue'
import DeviceDetail from '../components/DeviceDetail.vue'
import UsersPanel from '../components/UsersPanel.vue'
import BackupPanel from '../components/BackupPanel.vue'
import DeviceHistory from '../components/DeviceHistory.vue'
import { allTypeOptions } from '../utils/deviceTypes'

const router = useRouter()
const auth = useAuthStore()
const store = useDevicesStore()
const settings = useSettingsStore()
const external = useExternalStore()

const activeTab = ref('devices')
const viewMode = ref('tree')
const historyDevice = ref(null)
const detailDevice = ref(null)
const targetDialogVisible = ref(false)
const targetEditing = ref(null)
const targetForm = ref({ name: '', ip_address: '', domain: '', port: null })
const deviceDialogVisible = ref(false)
const deviceEditing = ref(null)
const deviceForm = ref({ name: '', type: 'group', ip_address: '', port: null, location: '' })
const deviceCandidates = ref([])
const isAdmin = computed(() => auth.user?.role === 'admin')

const typeOptions = computed(() => allTypeOptions(settings.builtinTypes, settings.customTypes))

let refreshTimer

onMounted(async () => {
  await auth.loadMe()
  await store.load()
  await external.load()
  if (auth.user?.role === 'admin') {
    await settings.loadInterval()
  }
  await settings.loadTypes()
  refreshTimer = setInterval(() => {
    store.load()
    external.load()
  }, 30000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})

function onLogout() {
  auth.logout()
  router.push('/login')
}

async function onCreateRoot() {
  try {
    const { value } = await ElMessageBox.prompt('请输入分组名称', '新增根分组', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '分组名称不能为空',
    })
    await store.create({ name: value, type: 'group' })
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.response?.data?.detail || '创建失败')
  }
}

async function onRecheckAll() {
  try {
    await Promise.all([store.recheckAll(), external.checkAll()])
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '巡检失败')
  }
}

async function onSaveInterval() {
  try {
    await settings.saveInterval(settings.pollIntervalMinutes)
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

function openCreateTarget() {
  targetEditing.value = null
  targetForm.value = { name: '', ip_address: '', domain: '', port: null }
  targetDialogVisible.value = true
}

function openEditTarget(t) {
  targetEditing.value = t
  targetForm.value = {
    name: t.name,
    ip_address: t.ip_address || '',
    domain: t.domain || '',
    port: t.port ?? null,
  }
  targetDialogVisible.value = true
}

async function onSaveTarget() {
  const payload = {
    name: targetForm.value.name,
    ip_address: targetForm.value.ip_address || null,
    domain: targetForm.value.domain || null,
    port: targetForm.value.port || null,
  }
  try {
    if (targetEditing.value) {
      await external.update(targetEditing.value.id, payload)
    } else {
      await external.create(payload)
    }
    targetDialogVisible.value = false
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

async function onDeleteTarget(t) {
  try {
    await ElMessageBox.confirm(`确定删除外网目标「${t.name}」？`, '删除确认')
  } catch (error) {
    return
  }
  try {
    await external.remove(t.id)
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

async function onExternalCheckAll() {
  try {
    await external.checkAll()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '检测失败')
  }
}

function collectDeviceDescendantIds(node, acc) {
  if (!node.children) return acc
  for (const c of node.children) {
    acc.add(c.id)
    collectDeviceDescendantIds(c, acc)
  }
  return acc
}

function openDeviceEdit(device) {
  const descendants = collectDeviceDescendantIds(device, new Set([device.id]))
  const candidates = []
  const walk = (nodes, depth) => {
    for (const n of nodes) {
      if (descendants.has(n.id)) continue
      candidates.push({ id: n.id, name: n.name, depth })
      if (n.children && n.children.length) walk(n.children, depth + 1)
    }
  }
  walk(store.tree, 0)
  deviceCandidates.value = candidates
  deviceEditing.value = device
  deviceForm.value = {
    name: device.name,
    type: device.type,
    ip_address: device.ip_address || '',
    port: device.port,
    location: device.location || '',
  }
  deviceDialogVisible.value = true
}

async function onSaveDevice() {
  const parentId = deviceEditing.value.parent_id
  const payload = {
    ...deviceForm.value,
    parent_id: parentId,
    ip_address: deviceForm.value.ip_address || null,
    port: deviceForm.value.port || null,
    location: deviceForm.value.location || null,
  }
  try {
    await store.update(deviceEditing.value.id, payload)
    deviceDialogVisible.value = false
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}
</script>

<template>
  <el-container class="layout">
    <el-header class="header">
      <span class="title">织网 WebWeaver</span>
      <span class="user-info">用户：{{ auth.user?.username }}（{{ auth.user?.role }}）</span>
      <el-button link @click="onLogout">退出登录</el-button>
    </el-header>
    <el-main>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="设备" name="devices">
          <el-card>
            <template #header>
              <div class="toolbar">
                <el-button type="primary" @click="onCreateRoot">
                  新增根分组
                </el-button>
                <el-button @click="store.load()">刷新</el-button>
                <el-button type="success" @click="onRecheckAll">立即巡检全部</el-button>
                <el-radio-group v-model="viewMode" size="small">
                  <el-radio-button value="tree">树形</el-radio-button>
                  <el-radio-button value="table">表格</el-radio-button>
                </el-radio-group>
                <div v-if="isAdmin" class="interval-setting">
                  <el-input-number
                    v-model="settings.pollIntervalMinutes"
                    :min="1"
                    :max="1440"
                    size="small"
                  />
                  <el-button size="small" @click="onSaveInterval">保存间隔</el-button>
                </div>
                <div class="stats">
                  <el-tag type="success">在线 {{ store.stats.online }}</el-tag>
                  <el-tag type="warning">警告 {{ store.stats.warning }}</el-tag>
                  <el-tag type="danger">离线 {{ store.stats.offline }}</el-tag>
                  <el-tag type="info">未知 {{ store.stats.unknown }}</el-tag>
                </div>
              </div>
            </template>
            <div v-if="viewMode === 'tree'" class="tree-scroll">
              <el-tree
                :data="store.tree"
                :props="{ label: 'name', children: 'children' }"
                node-key="id"
                default-expand-all
                :expand-on-click-node="false"
              >
                <template #default="{ data }">
                  <DeviceTree
                    :node="data"
                    @open-history="historyDevice = $event"
                    @open-detail="detailDevice = $event"
                  />
                </template>
              </el-tree>
            </div>
            <DeviceTable v-else :on-edit="openDeviceEdit" />
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="外网" name="external">
          <el-card>
            <template #header>
              <div class="toolbar">
                <el-button v-if="isAdmin" type="primary" @click="openCreateTarget">
                  新增外网目标
                </el-button>
                <el-button @click="external.load()">刷新</el-button>
                <el-button type="success" @click="onExternalCheckAll">立即检测</el-button>
              </div>
            </template>
            <table class="external-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>IP</th>
                  <th>IP 状态</th>
                  <th>IP 延时</th>
                  <th>域名</th>
                  <th>域名状态</th>
                  <th>域名延时</th>
                  <th v-if="isAdmin">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in external.targets" :key="t.id">
                  <td>{{ t.name }}</td>
                  <td>{{ t.ip_address || '-' }}</td>
                  <td>{{ t.ip_address ? t.ip_status : '-' }}</td>
                  <td>{{ t.ip_latency_ms != null ? t.ip_latency_ms + ' ms' : '-' }}</td>
                  <td>{{ t.domain || '-' }}</td>
                  <td>{{ t.domain ? t.domain_status : '-' }}</td>
                  <td>{{ t.domain_latency_ms != null ? t.domain_latency_ms + ' ms' : '-' }}</td>
                  <td v-if="isAdmin">
                    <el-button size="small" @click="openEditTarget(t)">编辑</el-button>
                    <el-button size="small" type="danger" @click="onDeleteTarget(t)">删除</el-button>
                  </td>
                </tr>
              </tbody>
            </table>
          </el-card>
        </el-tab-pane>
        <el-tab-pane v-if="isAdmin" label="用户管理" name="users">
          <UsersPanel />
        </el-tab-pane>
        <el-tab-pane v-if="isAdmin" label="备份与恢复" name="backup">
          <BackupPanel />
        </el-tab-pane>
      </el-tabs>

      <DeviceHistory
        v-if="historyDevice"
        :device="historyDevice"
        @close="historyDevice = null"
      />

      <DeviceDetail
        v-if="detailDevice"
        :device="detailDevice"
        @close="detailDevice = null"
        @updated="store.load()"
      />

      <el-dialog v-model="targetDialogVisible" :title="targetEditing ? '编辑外网目标' : '新增外网目标'">
        <el-form label-width="80px">
          <el-form-item label="名称">
            <el-input v-model="targetForm.name" />
          </el-form-item>
          <el-form-item label="IP 地址">
            <el-input v-model="targetForm.ip_address" placeholder="可选" />
          </el-form-item>
          <el-form-item label="域名">
            <el-input v-model="targetForm.domain" placeholder="可选" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="targetForm.port" :min="1" :max="65535" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="targetDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="onSaveTarget">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="deviceDialogVisible" title="编辑设备" width="460px">
        <el-form label-width="90px">
          <el-form-item label="名称">
            <el-input v-model="deviceForm.name" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="deviceForm.type" style="width: 100%">
              <el-option
                v-for="opt in typeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="IP 地址">
            <el-input v-model="deviceForm.ip_address" placeholder="留空表示纯分组节点" />
          </el-form-item>
          <el-form-item label="TCP 端口">
            <el-input-number v-model="deviceForm.port" :min="1" :max="65535" placeholder="可选" />
          </el-form-item>
          <el-form-item label="位置">
            <el-input v-model="deviceForm.location" placeholder="如：机房A/机架1（可选）" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="deviceDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="onSaveDevice">保存</el-button>
        </template>
      </el-dialog>
    </el-main>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
}
.title {
  font-weight: 600;
  font-size: 18px;
}
.user-info {
  margin-left: auto;
  color: #606266;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stats {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.tree-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
}
.tree-scroll :deep(.el-tree) {
  min-width: max-content;
}
.interval-setting {
  display: flex;
  align-items: center;
  gap: 8px;
}
.external-table {
  width: 100%;
  border-collapse: collapse;
}
.external-table th,
.external-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #eee;
  text-align: left;
}
.external-table th {
  color: #606266;
  font-weight: 600;
}
</style>
