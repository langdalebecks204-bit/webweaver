import client from './client'

export default {
  getLldpNeighbors() {
    return client.get('/topology/lldp-neighbors')
  },
  applyLldp(links, updateHierarchy = true) {
    return client.post('/topology/apply-lldp', {
      links,
      update_hierarchy: updateHierarchy,
    })
  },
}
