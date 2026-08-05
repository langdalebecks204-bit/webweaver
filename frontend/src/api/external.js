import client from './client'

export function fetchExternalTargets() {
  return client.get('/external')
}

export function createExternalTarget(payload) {
  return client.post('/external', payload)
}

export function updateExternalTarget(id, payload) {
  return client.put(`/external/${id}`, payload)
}

export function deleteExternalTarget(id) {
  return client.delete(`/external/${id}`)
}

export function checkAllExternalTargets() {
  return client.post('/external/check-all')
}