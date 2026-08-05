import { defineStore } from 'pinia'
import {
  checkAllExternalTargets,
  createExternalTarget,
  deleteExternalTarget,
  fetchExternalTargets,
  updateExternalTarget,
} from '../api/external'

export const useExternalStore = defineStore('external', {
  state: () => ({
    targets: [],
    loading: false,
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        this.targets = (await fetchExternalTargets()).data
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      const { data } = await createExternalTarget(payload)
      await this.load()
      return data
    },
    async update(id, payload) {
      const { data } = await updateExternalTarget(id, payload)
      await this.load()
      return data
    },
    async remove(id) {
      await deleteExternalTarget(id)
      await this.load()
    },
    async checkAll() {
      await checkAllExternalTargets()
      await this.load()
    },
  },
})