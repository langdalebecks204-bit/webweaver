import { defineStore } from 'pinia'
import { createUser, deleteUser, fetchUsers, updateUser } from '../api/users'

export const useUsersStore = defineStore('users', {
  state: () => ({
    users: [],
    loading: false,
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        this.users = (await fetchUsers()).data
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      const { data } = await createUser(payload)
      await this.load()
      return data
    },
    async update(id, payload) {
      const { data } = await updateUser(id, payload)
      await this.load()
      return data
    },
    async remove(id) {
      await deleteUser(id)
      await this.load()
    },
  },
})