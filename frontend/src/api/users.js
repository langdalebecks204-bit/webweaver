import client from './client'

export function fetchUsers() {
  return client.get('/users')
}

export function createUser(payload) {
  return client.post('/users', payload)
}

export function updateUser(id, payload) {
  return client.put(`/users/${id}`, payload)
}

export function deleteUser(id) {
  return client.delete(`/users/${id}`)
}