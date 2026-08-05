import client from './client'

export function login(payload) {
  return client.post('/auth/login', payload)
}

export function fetchMe() {
  return client.get('/auth/me')
}
