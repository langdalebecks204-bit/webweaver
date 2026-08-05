import { defineStore } from 'pinia'
import { fetchInspectionInterval, updateInspectionInterval } from '../api/settings'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    pollIntervalMinutes: 5,
    loading: false,
  }),
  actions: {
    async loadInterval() {
      this.loading = true
      try {
        const { data } = await fetchInspectionInterval()
        this.pollIntervalMinutes = data.poll_interval_minutes
      } finally {
        this.loading = false
      }
    },
    async saveInterval(minutes) {
      const { data } = await updateInspectionInterval(minutes)
      this.pollIntervalMinutes = data.poll_interval_minutes
    },
  },
})
