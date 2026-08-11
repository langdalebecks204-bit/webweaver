import client from './client'

export function exportBackup(params) {
  return client.get('/backup/export', { params, responseType: 'blob' })
}

export function importBackup(file, mode) {
  return client.post('/backup/import', file, {
    params: { mode },
    headers: { 'Content-Type': 'application/octet-stream' },
  })
}

export function resetData() {
  return client.post('/backup/reset')
}