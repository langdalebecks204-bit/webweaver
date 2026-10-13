export function findCoreSwitch(nodes) {
  if (!nodes || nodes.length === 0) return null
  // 1. 优先匹配名称包含“核心”且类型为交换机（switch）的设备
  const namedCore = nodes.find(
    (n) => n.type === 'switch' && n.name && n.name.toLowerCase().includes('核心')
  )
  if (namedCore) return namedCore.id

  // 2. 回退到列表中的第一个交换机
  const firstSwitch = nodes.find((n) => n.type === 'switch')
  if (firstSwitch) return firstSwitch.id

  // 3. 回退到第一个根节点或第一个设备
  return nodes[0].id
}

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
        port_bindings: node.port_bindings || {},
      })
      if (parentId !== null) {
        links.push({ source: parentId, target: node.id, status: node.status || 'unknown' })
      }
      if (childCount > 0) walk(node.children, node.id)
    }
  }
  walk(tree)

  if (nodes.length === 0) {
    return { nodes: [], links: [], coreNodeId: null }
  }

  const coreNodeId = findCoreSwitch(nodes)

  // 建立无向邻接表用于 BFS 计算层级
  const adj = new Map()
  for (const n of nodes) {
    adj.set(n.id, new Set())
  }
  for (const l of links) {
    const s = typeof l.source === 'object' ? l.source.id : l.source
    const t = typeof l.target === 'object' ? l.target.id : l.target
    if (adj.has(s) && adj.has(t)) {
      adj.get(s).add(t)
      adj.get(t).add(s)
    }
  }

  // BFS 计算各节点相对 coreNodeId 的跳数/层级
  const layers = new Map()
  const queue = []
  if (coreNodeId !== null && adj.has(coreNodeId)) {
    layers.set(coreNodeId, 0)
    queue.push(coreNodeId)
  }

  while (queue.length > 0) {
    const curr = queue.shift()
    const currLayer = layers.get(curr)
    for (const neighbor of adj.get(curr)) {
      if (!layers.has(neighbor)) {
        layers.set(neighbor, currLayer + 1)
        queue.push(neighbor)
      }
    }
  }

  // 处理未连通孤立节点：分配到当前最大层级 + 1
  let maxLayer = 0
  for (const layer of layers.values()) {
    if (layer > maxLayer) maxLayer = layer
  }
  for (const n of nodes) {
    if (!layers.has(n.id)) {
      layers.set(n.id, maxLayer + 1)
    }
  }

  // 按层级分组节点
  const layerGroups = new Map()
  for (const n of nodes) {
    const l = layers.get(n.id) ?? 1
    n.layer = l
    if (!layerGroups.has(l)) layerGroups.set(l, [])
    layerGroups.get(l).push(n)
  }

  // 极坐标计算布局
  for (const [layer, group] of layerGroups.entries()) {
    if (layer === 0) {
      // 核心节点位于原点 (0, 0)
      for (const node of group) {
        node.x = 0
        node.y = 0
        node.fx = 0
        node.fy = 0
      }
    } else {
      // 半径：内圈 200，外圈及后续按层级递增 180
      const radius = 200 + (layer - 1) * 180
      const count = group.length
      group.forEach((node, idx) => {
        const angle = (2 * Math.PI * idx) / count - Math.PI / 2
        const x = radius * Math.cos(angle)
        const y = radius * Math.sin(angle)
        node.x = x
        node.y = y
        node.fx = x
        node.fy = y
      })
    }
  }

  return { nodes, links, coreNodeId }
}