import { defineStore } from 'pinia'
import { login as apiLogin, fetchMe } from '../api/auth'

const TOKEN_KEY = 'weaver_token'
const CRED_KEY = 'weaver_saved_credentials'

function readToken() {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || ''
}

function writeToken(token, remember) {
  if (remember) {
    localStorage.setItem(TOKEN_KEY, token)
    sessionStorage.removeItem(TOKEN_KEY)
  } else {
    sessionStorage.setItem(TOKEN_KEY, token)
    localStorage.removeItem(TOKEN_KEY)
  }
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(TOKEN_KEY)
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: readToken(),
    user: null,
  }),
  actions: {
    async login(username, password, options = {}) {
      const { data } = await apiLogin({ username, password })
      this.token = data.access_token
      writeToken(data.access_token, options.rememberLogin !== false)
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
      clearToken()
    },
    saveCredentials(username, password) {
      localStorage.setItem(CRED_KEY, JSON.stringify({ username, password }))
    },
    loadCredentials() {
      const raw = localStorage.getItem(CRED_KEY)
      if (!raw) return null
      try {
        return JSON.parse(raw)
      } catch {
        return null
      }
    },
    clearCredentials() {
      localStorage.removeItem(CRED_KEY)
    },
  },
})