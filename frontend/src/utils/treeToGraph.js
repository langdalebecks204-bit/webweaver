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
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  // 建立无向邻接表用于构建以核心为根的生成树
  const adj = new Map()
  for (const n of nodes) {
    adj.set(n.id, [])
  }
  for (const l of links) {
    const s = typeof l.source === 'object' ? l.source.id : l.source
    const t = typeof l.target === 'object' ? l.target.id : l.target
    if (adj.has(s) && adj.has(t)) {
      adj.get(s).push(t)
      adj.get(t).push(s)
    }
  }

  // BFS 构建生成树与层级
  const layers = new Map()
  const treeChildren = new Map()
  for (const n of nodes) {
    treeChildren.set(n.id, [])
  }

  const visited = new Set()
  const queue = []

  if (coreNodeId !== null && adj.has(coreNodeId)) {
    layers.set(coreNodeId, 0)
    visited.add(coreNodeId)
    queue.push(coreNodeId)
  }

  while (queue.length > 0) {
    const curr = queue.shift()
    const currLayer = layers.get(curr)
    for (const neighbor of adj.get(curr)) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor)
        layers.set(neighbor, currLayer + 1)
        treeChildren.get(curr).push(neighbor)
        queue.push(neighbor)
      }
    }
  }

  // 处理未连通孤立节点：作为直连分支挂载
  const unvisited = nodes.filter((n) => !visited.has(n.id))
  for (const orphan of unvisited) {
    layers.set(orphan.id, 1)
    treeChildren.get(coreNodeId)?.push(orphan.id)
    visited.add(orphan.id)
  }

  // 计算子树权重（叶子节点数，最少为 1）
  const weightCache = new Map()
  function getSubtreeWeight(id) {
    if (weightCache.has(id)) return weightCache.get(id)
    const children = treeChildren.get(id) || []
    if (children.length === 0) {
      weightCache.set(id, 1)
      return 1
    }
    let sum = 0
    for (const cId of children) {
      sum += getSubtreeWeight(cId)
    }
    weightCache.set(id, sum)
    return sum
  }

  // 核心节点固定位于原点 (0, 0)
  const coreNode = nodeMap.get(coreNodeId)
  if (coreNode) {
    coreNode.x = 0
    coreNode.y = 0
    coreNode.fx = 0
    coreNode.fy = 0
    coreNode.layer = 0
  }

  // 递归按父子扇区分配各层同心圆坐标
  // 各层节点位于同心圆上：R_k = 220 + (k - 1) * 200
  function assignAngles(parentId, startAngle, endAngle) {
    const children = treeChildren.get(parentId) || []
    if (children.length === 0) return

    const totalWeight = children.reduce((acc, cId) => acc + getSubtreeWeight(cId), 0)
    let currentAngle = startAngle

    for (const cId of children) {
      const childWeight = getSubtreeWeight(cId)
      const sectorSpan = (endAngle - startAngle) * (childWeight / totalWeight)
      const midAngle = currentAngle + sectorSpan / 2
      const childLayer = layers.get(cId) ?? 1

      const radius = 220 + (childLayer - 1) * 200
      const x = radius * Math.cos(midAngle)
      const y = radius * Math.sin(midAngle)

      const childNode = nodeMap.get(cId)
      if (childNode) {
        childNode.x = x
        childNode.y = y
        childNode.fx = x
        childNode.fy = y
        childNode.layer = childLayer
      }

      assignAngles(cId, currentAngle, currentAngle + sectorSpan)
      currentAngle += sectorSpan
    }
  }

  if (coreNodeId !== null) {
    assignAngles(coreNodeId, -Math.PI / 2, (3 * Math.PI) / 2)
  }

  for (const n of nodes) {
    if (n.layer === undefined) {
      n.layer = layers.get(n.id) ?? 1
    }
  }

  return { nodes, links, coreNodeId }
}