import client from './client'

export function exportBackup(params) {
  return client.get('/backup/export', { params })
}

export function importBackup(data, mode) {
  return client.post('/backup/import', data, { params: { mode } })
}

export function resetData() {
  return client.post('/backup/reset')
}