<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSystemStore } from '../stores/system'

const store = useSystemStore()

const updating = ref(false)
const updateStep = ref(0)
const statusMessage = ref('')
const checkedOnce = ref(false)

const mirrorOptions = [
  { label: 'ghproxy.net (推荐国内用户)', value: 'https://ghproxy.net/' },
  { label: 'gh-proxy.com (备用国内镜像)', value: 'https://gh-proxy.com/' },
  { label: '官方直连 (GitHub)', value: '' },
  { label: '自定义代理前缀', value: 'custom' },
]

const formattedSize = computed(() => {
  if (!store.packageSize) return ''
  const mb = store.packageSize / 1024 / 1024
  return `${mb.toFixed(2)} MB`
})

onMounted(async () => {
  if (!store.currentVersion) {
    try {
      await store.check()
      checkedOnce.value = true
    } catch (_) {
      // ignore on initial silent mount
    }
  }
})

async function onCheck() {
  try {
    await store.check()
    checkedOnce.value = true
    if (!store.hasUpdate) {
      ElMessage.success('当前已是最新版本！')
    } else {
      ElMessage.info(`发现新版本 v${store.latestVersion}`)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '检查更新失败，请检查网络或切换加速镜像。')
  }
}

async function onApply() {
  try {
    await ElMessageBox.confirm(
      `确定升级到版本 v${store.latestVersion} 吗？系统将下载差量包并自动重启服务（预计 3~5 秒），期间连接将短暂中断。`,
      '系统差量更新确认',
      {
        confirmButtonText: '立即升级',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  updating.value = true
  updateStep.value = 1
  statusMessage.value = '正在下载更新包并执行安全校验与部署...'

  try {
    await store.apply()
    updateStep.value = 2
    statusMessage.value = '更新已成功应用，正在重启服务并等待重新就绪...'

    await store.waitForHealth(35, 1000)
    updateStep.value = 3
    statusMessage.value = '升级成功！系统已就绪，正在刷新进入新版本...'

    setTimeout(() => {
      window.location.reload()
    }, 1500)
  } catch (error) {
    updating.value = false
    ElMessage.error(error.message || error.response?.data?.detail || '升级或重启检测失败，请稍后重试。')
  }
}
</script>

<template>
  <div class="update-panel">
    <el-card class="section">
      <template #header>
        <div class="card-header">
          <span>系统差量更新</span>
          <el-tag type="info">Docker 容器模式</el-tag>
        </div>
      </template>

      <div class="version-row">
        <div class="info-item">
          <span class="label">当前运行版本：</span>
          <el-tag size="large" type="primary" effect="dark">
            v{{ store.currentVersion || '0.5.4' }}
          </el-tag>
        </div>

        <div class="mirror-item">
          <span class="label">下载加速镜像：</span>
          <el-select v-model="store.selectedMirror" style="width: 260px" size="default">
            <el-option
              v-for="opt in mirrorOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </div>

        <div v-if="store.selectedMirror === 'custom'" class="custom-mirror-item">
          <el-input
            v-model="store.customMirror"
            placeholder="如 https://ghfast.top/"
            style="width: 260px"
          />
        </div>

        <el-button
          type="primary"
          :loading="store.checking"
          @click="onCheck"
        >
          检查更新
        </el-button>
      </div>

      <div v-if="checkedOnce && !store.hasUpdate" class="up-to-date-box">
        <el-tag type="success" size="large">✓ 当前已是最新版本，无需更新</el-tag>
      </div>
    </el-card>

    <el-card v-if="store.hasUpdate" class="section update-available">
      <template #header>
        <div class="card-header">
          <span class="has-update-title">✨ 发现新版本</span>
          <el-tag type="success" effect="dark" size="large">v{{ store.latestVersion }}</el-tag>
        </div>
      </template>

      <div class="update-meta">
        <div v-if="formattedSize" class="meta-item">
          <span class="meta-label">差量安装包体积：</span>
          <span class="meta-value">{{ formattedSize }}</span>
        </div>
        <div v-if="store.publishedAt" class="meta-item">
          <span class="meta-label">发布时间：</span>
          <span class="meta-value">{{ new Date(store.publishedAt).toLocaleString() }}</span>
        </div>
      </div>

      <div class="release-notes-box">
        <div class="notes-header">版本更新内容：</div>
        <pre class="notes-content">{{ store.releaseNotes || '无发布日志说明。' }}</pre>
      </div>

      <div class="action-footer">
        <el-button
          type="success"
          size="large"
          :loading="updating"
          @click="onApply"
        >
          一键差量热更新
        </el-button>
        <span class="tip-text">更新仅替换前后端源码与静态文件，数据库配置与持久化数据不受影响。</span>
      </div>
    </el-card>

    <!-- 升级进度弹窗 -->
    <el-dialog
      v-model="updating"
      title="系统平滑升级中"
      width="480px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div class="updating-content">
        <div class="spinner-box">
          <el-progress
            type="circle"
            :percentage="updateStep === 1 ? 35 : updateStep === 2 ? 75 : 100"
            :status="updateStep === 3 ? 'success' : undefined"
          />
        </div>
        <p class="status-msg">{{ statusMessage }}</p>
        <p class="sub-msg">服务重启期间网页将短暂断开，恢复后将自动刷新，请勿关闭本窗口...</p>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.update-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 8px;
}

.section {
  border-radius: 6px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.version-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 18px;
}

.info-item, .mirror-item, .custom-mirror-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 14px;
  color: #606266;
}

.up-to-date-box {
  margin-top: 18px;
}

.update-available {
  border: 1px solid #67c23a;
}

.has-update-title {
  color: #67c23a;
  font-size: 16px;
}

.update-meta {
  display: flex;
  gap: 24px;
  margin-bottom: 14px;
  font-size: 14px;
  color: #606266;
}

.meta-value {
  font-weight: 500;
  color: #303133;
}

.release-notes-box {
  background: #f8f9fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 20px;
}

.notes-header {
  font-weight: 600;
  margin-bottom: 8px;
  font-size: 14px;
  color: #303133;
}

.notes-content {
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #4a5568;
  margin: 0;
  max-height: 240px;
  overflow-y: auto;
}

.action-footer {
  display: flex;
  align-items: center;
  gap: 16px;
}

.tip-text {
  font-size: 12px;
  color: #909399;
}

.updating-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 16px 0;
}

.spinner-box {
  margin-bottom: 16px;
}

.status-msg {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.sub-msg {
  font-size: 12px;
  color: #909399;
  margin: 0;
}
</style>
