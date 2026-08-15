export function treeToGraph(tree) {
  const nodes = []
  const links = []
  function walk(items, parentId = null) {
    for (const node of items) {
      const childCount = node.children ? node.children.length : 0
      nodes.push({
        id: node.id,
        name: node.name,
        type: node.type,
        status: node.type === 'group' ? 'unknown' : node.status || 'unknown',
        latency_ms: node.latency_ms ?? null,
        ip_address: node.ip_address || '',
        val: childCount * 3 + 8,
      })
      if (parentId !== null) {
        links.push({ source: parentId, target: node.id, status: node.status || 'unknown' })
      }
      if (childCount > 0) walk(node.children, node.id)
    }
  }
  walk(tree)
  return { nodes, links }
}