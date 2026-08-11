export function updateStatus(tree, nodeId, patch) {
  return tree.map((node) => {
    if (node.id === nodeId) return { ...node, ...patch }
    if (node.children && node.children.length) {
      return { ...node, children: updateStatus(node.children, nodeId, patch) }
    }
    return node
  })
}

export function removeNode(tree, nodeId) {
  const result = []
  for (const node of tree) {
    if (node.id === nodeId) continue
    if (node.children && node.children.length) {
      result.push({ ...node, children: removeNode(node.children, nodeId) })
    } else {
      result.push(node)
    }
  }
  return result
}

export function flattenTree(tree) {
  const out = []
  const parentName = new Map()
  const walk = (nodes) => {
    for (const n of nodes) {
      const parent = n.parent_id != null ? parentName.get(n.parent_id) || '' : ''
      out.push({ ...n, parentName: parent })
      parentName.set(n.id, n.name)
      if (n.children && n.children.length) walk(n.children)
    }
  }
  walk(tree)
  return out
}

export function filterDevices(flat, { keyword = '', status = '' } = {}) {
  const kw = keyword.trim().toLowerCase()
  return flat.filter((d) => {
    if (status && d.status !== status) return false
    if (!kw) return true
    return (
      d.name.toLowerCase().includes(kw) ||
      (d.ip_address || '').toLowerCase().includes(kw) ||
      (d.location || '').toLowerCase().includes(kw)
    )
  })
}
