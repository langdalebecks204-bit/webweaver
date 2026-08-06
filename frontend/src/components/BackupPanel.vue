<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { exportBackup, importBackup, resetData } from '../api/backup'
import { useAuthStore } from '../stores/auth'
import { useDevicesStore } from '../stores/devices'
import { useExternalStore } from '../stores/external'
import { useSettingsStore } from '../stores/settings'

const router = useRouter()
const auth = useAuthStore()
const devices = useDevicesStore()
const external = useExternalStore()
const settings = useSettingsStore()

const includeDevices = ref(true)
const includeExternal = ref(true)
const includeSettings = ref(true)
const importMode = ref('replace')

async function onExport() {
  try {
    const { data } = await exportBackup({
      include_devices: includeDevices.value,
      include_external: includeExternal.value,
      include_settings: includeSettings.value,
    })
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const stamp = new Date().toISOString().replace(/[:.]/g, '-')
    a.href = url
    a.download = `weaver-backup-${stamp}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导出失败')
  }
}

async function onImport(file) {
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    await importBackup(data, importMode.value)
    await Promise.all([devices.load(), external.load()])
    if (auth.user?.role === 'admin') await settings.loadInterval()
    ElMessage.success('导入成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

function onFileChange(event) {
  const file = event.target.files[0]
  if (file) onImport(file)
}

async function onReset() {
  let value
  try {
    const result = await ElMessageBox.prompt(
      '输入 "clear" 确认清除所有数据',
      '危险操作',
      { inputPattern: /^clear$/, inputErrorMessage: '请输入 clear' }
    )
    value = result.value
  } catch (error) {
    return
  }
  if (value !== 'clear') return
  try {
    await resetData()
    auth.logout()
    router.push('/login')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '清除失败')
  }
}
</script>

<template>
  <div class="backup-panel">
    <el-card class="section">
      <template #header>导出备份</template>
      <div class="checks">
        <label><input type="checkbox" v-model="includeDevices" /> 设备</label>
        <label><input type="checkbox" v-model="includeExternal" /> 外网目标</label>
        <label><input type="checkbox" v-model="includeSettings" /> 巡检间隔</label>
      </div>
      <el-button type="primary" @click="onExport">导出备份</el-button>
    </el-card>

    <el-card class="section">
      <template #header>导入备份</template>
      <div class="mode">
        <label><input type="radio" value="replace" v-model="importMode" /> 替换</label>
        <label><input type="radio" value="merge" v-model="importMode" /> 合并</label>
      </div>
      <input class="file-input" type="file" accept="application/json,.json" @change="onFileChange" />
    </el-card>

    <el-card class="section danger">
      <template #header>危险操作</template>
      <p>清除所有数据将清空设备、外网目标、设置与所有用户，仅保留默认 admin。</p>
      <el-button type="danger" @click="onReset">清除所有数据（初始化）</el-button>
    </el-card>
  </div>
</template>