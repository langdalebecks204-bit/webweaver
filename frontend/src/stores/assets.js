import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import assetsApi from '../api/assets'

export const useAssetsStore = defineStore('assets', () => {
  const items = ref([])
  const loading = ref(false)
  const scanning = ref(false)
  const selectedCollectorId = ref(null)

  const totalCount = computed(() => items.value.length)
  const managedCount = computed(() => items.value.filter((i) => i.is_managed).length)
  const unmanagedCount = computed(() => items.value.filter((i) => !i.is_managed).length)

  const vendorStats = computed(() => {
    const counts = {}
    for (const item of items.value) {
      const v = item.vendor || '未知厂商'
      counts[v] = (counts[v] || 0) + 1
    }
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
  })

  async function load(collectorId = null) {
    loading.value = true
    try {
      const targetId = collectorId !== null ? collectorId : selectedCollectorId.value
      const res = await assetsApi.getAssets(targetId)
      items.value = res.data || []
    } finally {
      loading.value = false
    }
  }

  async function scan(collectorId = null) {
    scanning.value = true
    try {
      const targetId = collectorId !== null ? collectorId : selectedCollectorId.value
      const res = await assetsApi.scanAssets(targetId)
      items.value = res.data || []
    } finally {
      scanning.value = false
    }
  }

  async function enroll(payload) {
    const res = await assetsApi.enrollAsset(payload)
    // Reload assets to reflect changes
    await load()
    return res.data
  }

  return {
    items,
    loading,
    scanning,
    selectedCollectorId,
    totalCount,
    managedCount,
    unmanagedCount,
    vendorStats,
    load,
    scan,
    enroll,
  }
})
