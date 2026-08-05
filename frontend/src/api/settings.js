import client from './client'

export function fetchInspectionInterval() {
  return client.get('/settings/inspection-interval')
}

export function updateInspectionInterval(minutes) {
  return client.put('/settings/inspection-interval', { poll_interval_minutes: minutes })
}
