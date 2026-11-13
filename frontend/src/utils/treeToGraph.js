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

export const DEFAULT_INFRASTRUCTURE_TYPES = [
  'switch',
  'unmanaged_switch',
  'router',
  'firewall',
  'ap',
  'server',
  'nas',
  'nvr',
  'ups',
]

export const TERMINAL_TYPES = ['terminal', 'camera', 'printer']

export function hasAllowedDescendant(item, allowedSet) {
  if (!allowedSet) return true
  if (item.type !== 'group' && allowedSet.has(item.type)) return true
  if (!item.children || item.children.length === 0) return false
  return item.children.some((child) => hasAllowedDescendant(child, allowedSet))
}

export function treeToGraph(tree, options = {}) {
  const allowedSet = options.allowedTypes ? new Set(options.allowedTypes) : null
  const nodes = []
  const links = []

  function walk(items, parentId = null) {
    for (const node of items || []) {
      if (node.type === 'group') {
        if (allowedSet && !hasAllowedDescendant(node, allowedSet)) {
          continue
        }
      } else if (allowedSet && !allowedSet.has(node.type)) {
        if (node.children && node.children.length > 0) {
          walk(node.children, parentId)
        }
        continue
      }

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
        let sourcePort = null
        let targetPort = node.uplink_port ? `P${node.uplink_port}` : null

        // Check if parent has port binding pointing to this child
        const parentNode = nodes.find((n) => n.id === parentId)
        if (parentNode && parentNode.port_bindings) {
          for (const [pKey, binding] of Object.entries(parentNode.port_bindings)) {
            if (binding && binding.target_id === node.id) {
              sourcePort = `P${pKey}`
              break
            }
          }
        }

        // Check if child has port binding pointing to parent
        if (!targetPort && node.port_bindings) {
          for (const [pKey, binding] of Object.entries(node.port_bindings)) {
            if (binding && binding.target_id === parentId) {
              targetPort = `P${pKey}`
              break
            }
          }
        }

        links.push({
          source: parentId,
          target: node.id,
          status: node.status || 'unknown',
          source_port: sourcePort,
          target_port: targetPort,
        })
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

/**
 * Top-Down Hierarchical layout for Classic Visio mode.
 * Assigns static fx and fy based on tree depth and subtree bounds.
 */
export function applyVisioHierarchicalLayout(nodes, links) {
  if (!nodes || nodes.length === 0) return

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const childrenMap = new Map(nodes.map((n) => [n.id, []]))
  const parentMap = new Map()

  function getNodeId(endpoint) {
    if (typeof endpoint === 'object' && endpoint !== null) return endpoint.id
    return endpoint
  }

  for (const l of links || []) {
    const s = getNodeId(l.source)
    const t = getNodeId(l.target)
    if (nodeMap.has(s) && nodeMap.has(t) && s !== t) {
      if (!parentMap.has(t)) {
        parentMap.set(t, s)
        childrenMap.get(s).push(t)
      }
    }
  }

  // Identify root nodes (nodes without parent in links)
  let roots = nodes.filter((n) => !parentMap.has(n.id)).map((n) => n.id)
  if (roots.length === 0 && nodes.length > 0) {
    const coreCandidate = nodes.find((n) => n.role === 'gateway' || n.role === 'core')
    roots = [coreCandidate ? coreCandidate.id : nodes[0].id]
  }

  const spanningTreeChildren = new Map(nodes.map((n) => [n.id, []]))
  const depthMap = new Map()
  const visited = new Set()

  // BFS to assign depths and build an acyclic spanning tree
  const queue = []
  for (const rId of roots) {
    depthMap.set(rId, 0)
    visited.add(rId)
    queue.push(rId)
  }

  while (queue.length > 0) {
    const currId = queue.shift()
    const d = depthMap.get(currId) || 0
    const children = childrenMap.get(currId) || []
    for (const cId of children) {
      if (!visited.has(cId)) {
        visited.add(cId)
        depthMap.set(cId, d + 1)
        spanningTreeChildren.get(currId).push(cId)
        queue.push(cId)
      }
    }
  }

  // Handle any remaining unvisited nodes (e.g. disconnected components or isolated cycles)
  for (const n of nodes) {
    if (!visited.has(n.id)) {
      depthMap.set(n.id, 1)
      visited.add(n.id)
      roots.push(n.id)
      queue.push(n.id)
      while (queue.length > 0) {
        const currId = queue.shift()
        const d = depthMap.get(currId) || 1
        const children = childrenMap.get(currId) || []
        for (const cId of children) {
          if (!visited.has(cId)) {
            visited.add(cId)
            depthMap.set(cId, d + 1)
            spanningTreeChildren.get(currId).push(cId)
            queue.push(cId)
          }
        }
      }
    }
  }

  // Calculate subtree widths using spanningTreeChildren with recursion guard
  const widthMap = new Map()
  const NODE_MIN_WIDTH = 130
  const calcVisited = new Set()

  function calcSubtreeWidth(id) {
    if (calcVisited.has(id)) return widthMap.get(id) || NODE_MIN_WIDTH
    calcVisited.add(id)
    const children = spanningTreeChildren.get(id) || []
    if (children.length === 0) {
      widthMap.set(id, NODE_MIN_WIDTH)
      return NODE_MIN_WIDTH
    }
    let total = 0
    for (const cId of children) {
      total += calcSubtreeWidth(cId)
    }
    const w = Math.max(NODE_MIN_WIDTH, total)
    widthMap.set(id, w)
    return w
  }

  roots.forEach((rId) => calcSubtreeWidth(rId))

  // Assign X and Y
  const LEVEL_HEIGHT = 150
  const xMap = new Map()

  function assignPositions(id, left, right) {
    const x = (left + right) / 2
    xMap.set(id, x)

    const children = spanningTreeChildren.get(id) || []
    if (children.length === 0) return

    let curLeft = left
    const totalChildWidth = children.reduce((sum, cId) => sum + (widthMap.get(cId) || NODE_MIN_WIDTH), 0)
    // If allocated width is larger than totalChildWidth, center children within allocated space
    if (right - left > totalChildWidth) {
      curLeft = left + (right - left - totalChildWidth) / 2
    }

    for (const cId of children) {
      const cWidth = widthMap.get(cId) || NODE_MIN_WIDTH
      assignPositions(cId, curLeft, curLeft + cWidth)
      curLeft += cWidth
    }
  }

  let rootLeft = 0
  for (const rId of roots) {
    const rWidth = widthMap.get(rId) || NODE_MIN_WIDTH
    assignPositions(rId, rootLeft, rootLeft + rWidth)
    rootLeft += rWidth + 40
  }

  // Center around 0
  let minX = Infinity
  let maxX = -Infinity
  for (const x of xMap.values()) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
  }
  const centerX = (minX + maxX) / 2

  for (const n of nodes) {
    const d = depthMap.get(n.id) || 0
    const rawX = xMap.get(n.id) ?? 0
    const finalX = Math.round(rawX - centerX)
    const finalY = d * LEVEL_HEIGHT + 60

    n.visioX = finalX
    n.visioY = finalY
    n.visioDepth = d

    n.x = finalX
    n.y = finalY
    n.fx = finalX
    n.fy = finalY
  }
}

/**
 * Clears rigid Visio layout coordinates so force-directed animation can resume.
 */
export function clearVisioLayout(nodes) {
  if (!nodes) return
  for (const n of nodes) {
    delete n.fx
    delete n.fy
  }
}
