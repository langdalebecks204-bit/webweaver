import { defineStore } from 'pinia'
import {
  addDeviceType,
  fetchDeviceTypes,
  fetchInspectionInterval,
  fetchPingParams,
  removeDeviceType,
  updateInspectionInterval,
  updatePingParams,
} from '../api/settings'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    pollIntervalMinutes: 5,
    loading: false,
    builtinTypes: [],
    customTypes: [],
    typesLoaded: false,
    pingCount: 3,
    pingPacketSize: 56,
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
    async loadTypes() {
      const { data } = await fetchDeviceTypes()
      this.builtinTypes = data.builtin
      this.customTypes = data.custom
      this.typesLoaded = true
    },
    async addType(name) {
      await addDeviceType(name)
      await this.loadTypes()
    },
    async removeType(name) {
      await removeDeviceType(name)
      await this.loadTypes()
    },
    async loadPingParams() {
      const { data } = await fetchPingParams()
      this.pingCount = data.ping_count
      this.pingPacketSize = data.ping_packet_size
    },
    async savePingParams(count, size) {
      const { data } = await updatePingParams(count, size)
      this.pingCount = data.ping_count
      this.pingPacketSize = data.ping_packet_size
    },
  },
})