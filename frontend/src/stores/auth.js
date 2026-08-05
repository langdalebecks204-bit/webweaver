import { defineStore } from 'pinia'
import { login as apiLogin, fetchMe } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('weaver_token') || '',
    user: null,
  }),
  actions: {
    async login(username, password) {
      const { data } = await apiLogin({ username, password })
      this.token = data.access_token
      localStorage.setItem('weaver_token', data.access_token)
      this.user = (await fetchMe()).data
    },
    async loadMe() {
      if (this.token && !this.user) {
        this.user = (await fetchMe()).data
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('weaver_token')
    },
  },
})
