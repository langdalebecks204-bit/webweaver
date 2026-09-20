import { defineStore } from 'pinia'
import { ref } from 'vue'
import { applyUpdate, checkUpdate, healthCheck } from '../api/system'

export const useSystemStore = defineStore('system', () => {
  const currentVersion = ref('')
  const latestVersion = ref('')
  const hasUpdate = ref(false)
  const releaseNotes = ref('')
  const publishedAt = ref('')
  const downloadUrl = ref('')
  const packageSize = ref(0)
  const checking = ref(false)
  const selectedMirror = ref('https://ghproxy.net/')
  const customMirror = ref('')

  async function check() {
    checking.value = true
    try {
      const mirror = selectedMirror.value === 'custom' ? customMirror.value : selectedMirror.value
      const res = await checkUpdate(mirror)
      const data = res.data
      currentVersion.value = data.current_version
      latestVersion.value = data.latest_version
      hasUpdate.value = data.has_update
      releaseNotes.value = data.release_notes
      publishedAt.value = data.published_at
      downloadUrl.value = data.download_url
      packageSize.value = data.size
      return data
    } finally {
      checking.value = false
    }
  }

  async function apply() {
    const mirror = selectedMirror.value === 'custom' ? customMirror.value : selectedMirror.value
    return await applyUpdate(downloadUrl.value, mirror)
  }

  async function waitForHealth(maxAttempts = 30, intervalMs = 1000) {
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, intervalMs))
      try {
        const res = await healthCheck()
        if (res.status === 200) {
          return true
        }
      } catch (e) {
        // service is restarting, keep waiting
      }
    }
    throw new Error('等待服务重启超时，请手动刷新页面。')
  }

  return {
    currentVersion,
    latestVersion,
    hasUpdate,
    releaseNotes,
    publishedAt,
    downloadUrl,
    packageSize,
    checking,
    selectedMirror,
    customMirror,
    check,
    apply,
    waitForHealth,
  }
})
