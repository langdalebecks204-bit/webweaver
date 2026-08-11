<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchDeviceHistory } from '../api/devices'
import { uploadDeviceImage, deleteDeviceImage } from '../api/devices'
import { useAuthStore } from '../stores/auth'

const props = defineProps({ device: { type: Object, required: true } })
const emit = defineEmits(['close'])

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const records = ref([])
const days = ref(30)
const activeTab = ref('history')
const page = ref(1)
const pageSize = 10
const uploading = ref(false)
const fileInput = ref(null)

const historyDays = ref(30)

async function loadHistory() {
  const { data } = await fetchDeviceHistory(props.device.id, historyDays.value)
  records.value = data.records
}

const pageCount = computed(() => Math.max(1, Math.ceil(records.value.length / pageSize)))
const pagedRecords = computed(() => {
  const start = (page.value - 1) * pageSize
  return records.value.slice(start, start + pageSize)
})

const stats = computed(() => {
  const recs = records.value
  const online = recs.filter((r) => r.status === 'online').length
  const offline = recs.filter((r) => r.status === 'offline').length
  const lastOffline = recs
    .filter((r) => r.status === 'offline')
    .map((r) => r.checked_at)
    .sort()
    .pop() || null
  const rate = recs.length ? Math.round((online / recs.length) * 100) : 0
  return { online, offline, lastOffline, rate }
})

function onChangeRecord() {
  page.value = 1
}

watch(historyDays, () => {
  loadHistory()
  onChangeRecord()
})

onMounted(loadHistory)

async function onPickImage() {
  fileInput.value?.click()
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const { data } = await uploadDeviceImage(props.device.id, file)
    emit('updated', data)
    ElMessage.success('图片已更新')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}

async function onRemoveImage() {
  try {
    await ElMessageBox.confirm('确定删除设备图片？', '删除确认')
  } catch {
    return
  }
  try {
    const { data } = await deleteDeviceImage(props.device.id)
    emit('updated', data)
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}
</script>

<template>
  <el-dialog
    :model-value="true"
    :title="`设备详情 - ${props.device.name}`"
    width="820px"
    @close="emit('close')"
    @closed="fileInput = null"
  >
    <div class="detail">
      <div class="left">
        <div class="image-box">
          <img
            v-if="props.device.image_url"
            :src="props.device.image_url"
            alt="设备图片"
            class="device-img"
          />
          <div v-else class="no-img">暂无图片</div>
          <div v-if="isAdmin" class="image-actions">
            <el-button size="small" type="primary" plain :loading="uploading" @click="onPickImage">
              上传/更换
            </el-button>
            <el-button
              v-if="props.device.image_url"
              size="small"
              type="danger"
              plain
              @click="onRemoveImage"
            >
              删除
            </el-button>
            <input
              ref="fileInput"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
              style="display: none"
              @change="onFileChange"
            />
          </div>
        </div>
        <ul class="info">
          <li><span class="k">类型</span>{{ props.device.type }}</li>
          <li><span class="k">IP 地址</span>{{ props.device.ip_address || '-' }}</li>
          <li><span class="k">端口</span>{{ props.device.port ?? '-' }}</li>
          <li><span class="k">位置</span>{{ props.device.location || '-' }}</li>
          <li><span class="k">状态</span>{{ props.device.status }}</li>
          <li><span class="k">延时</span>{{ props.device.latency_ms != null ? props.device.latency_ms + ' ms' : '-' }}</li>
        </ul>
      </div>
      <div class="right">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="历史记录" name="history">
            <div class="history-controls">
              <el-select v-model="historyDays" style="width: 130px">
                <el-option label="最近 7 天" :value="7" />
                <el-option label="最近 30 天" :value="30" />
                <el-option label="最近 90 天" :value="90" />
              </el-select>
            </div>
            <el-table :data="pagedRecords" size="small">
              <el-table-column prop="checked_at" label="时间">
                <template #default="{ row }">
                  {{ new Date(row.checked_at).toLocaleString() }}
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'online' ? 'success' : row.status === 'offline' ? 'danger' : 'warning'" size="small">
                    {{ row.status === 'online' ? '在线' : row.status === 'offline' ? '离线' : '警告' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="latency_ms" label="延时(ms)" width="100">
                <template #default="{ row }">{{ row.latency_ms ?? '-' }}</template>
              </el-table-column>
            </el-table>
            <el-pagination
              class="pager"
              layout="prev, pager, next"
              :total="records.length"
              :page-size="pageSize"
              :current-page="page"
              @current-change="page = $event"
            />
          </el-tab-pane>
          <el-tab-pane label="统计" name="stats">
            <div class="stats-grid">
              <div class="stat">
                <div class="val success">{{ stats.online }}</div>
                <div class="label">上线次数</div>
              </div>
              <div class="stat">
                <div class="val danger">{{ stats.offline }}</div>
                <div class="label">离线次数</div>
              </div>
              <div class="stat">
                <div class="val">{{ stats.lastOffline ? new Date(stats.lastOffline).toLocaleString() : '-' }}</div>
                <div class="label">最近离线</div>
              </div>
              <div class="stat">
                <div class="val">{{ stats.rate }}%</div>
                <div class="label">在线率</div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.detail {
  display: flex;
  gap: 20px;
}
.left {
  width: 240px;
  flex-shrink: 0;
}
.image-box {
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 8px;
  text-align: center;
  margin-bottom: 12px;
}
.device-img {
  max-width: 100%;
  max-height: 180px;
  border-radius: 4px;
}
.no-img {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 13px;
}
.image-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  justify-content: center;
}
.info {
  list-style: none;
  padding: 0;
  margin: 0;
}
.info li {
  padding: 6px 0;
  border-bottom: 1px solid #f5f7fa;
  font-size: 13px;
}
.info .k {
  display: inline-block;
  width: 64px;
  color: #909399;
}
.right {
  flex: 1;
  min-width: 0;
}
.history-controls {
  margin-bottom: 8px;
}
.pager {
  margin-top: 8px;
  justify-content: flex-end;
}
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.stat {
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 16px;
  text-align: center;
}
.stat .val {
  font-size: 22px;
  font-weight: 600;
  margin-bottom: 6px;
  word-break: break-all;
}
.stat .val.success {
  color: #67c23a;
}
.stat .val.danger {
  color: #f56c6c;
}
.stat .label {
  color: #909399;
  font-size: 12px;
}
</style>