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
