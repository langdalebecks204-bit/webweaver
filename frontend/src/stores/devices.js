import { defineStore } from 'pinia'
import {
  createDevice,
  deleteDevice,
  fetchTree,
  recheckDevice,
  updateDevice,
} from '../api/devices'
import { removeNode, updateStatus } from './devicesHelpers'

export const useDevicesStore = defineStore('devices', {
  state: () => ({
    tree: [],
    loading: false,
    lastUpdated: null,
  }),
  getters: {
    stats(state) {
      const counts = { online: 0, offline: 0, warning: 0, unknown: 0 }
      const walk = (nodes) => {
        for (const node of nodes) {
          counts[node.status] = (counts[node.status] || 0) + 1
          if (node.children && node.children.length) walk(node.children)
        }
      }
      walk(state.tree)
      return counts
    },
  },
  actions: {
    async load() {
      this.loading = true
      try {
        this.tree = (await fetchTree()).data
        this.lastUpdated = new Date()
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      const { data } = await createDevice(payload)
      await this.load()
      return data
    },
    async update(id, payload) {
      const { data } = await updateDevice(id, payload)
      await this.load()
      return data
    },
    async remove(id) {
      await deleteDevice(id)
      await this.load()
    },
    async recheck(id) {
      await recheckDevice(id)
      await this.load()
    },
    applyStatus(nodeId, status, latencyMs, lastCheck) {
      this.tree = updateStatus(this.tree, nodeId, { status, latencyMs, lastCheck })
    },
  },
})
