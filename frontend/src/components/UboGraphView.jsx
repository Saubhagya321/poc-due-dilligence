import { useMemo } from 'react'
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow'
import 'reactflow/dist/style.css'

// Mirrors the backend colour rules so a non-Indian jurisdiction or a
// foreign_entity type always wins over the entity-type palette.
function nodeColor(node) {
  if (node.jurisdiction && node.jurisdiction.trim().toLowerCase() !== 'india') {
    return { bg: '#ffebe9', border: '#cf222e' }
  }
  switch (node.entity_type) {
    case 'natural_person':
    case 'listed':
    case 'government':
      return { bg: '#e6f4ea', border: '#1a7f37' }
    case 'company':
    case 'llp':
    case 'trust':
    case 'huf':
      return { bg: '#fff4ce', border: '#b08800' }
    default:
      return { bg: '#f0f4f8', border: '#8c8c8c' }
  }
}

// Simple top-down breadth-first layout. Levels of equal depth are placed
// in a row; horizontal spacing scales with the widest level.
function layoutTree(root) {
  const nodes = []
  const edges = []
  const levels = []  // index = depth, value = array of {id, data, parentId}
  let idCounter = 0

  function walk(node, depth, parentId) {
    const id = `n${idCounter++}`
    if (!levels[depth]) levels[depth] = []
    levels[depth].push({ id, node, parentId })
    for (const child of node.children || []) walk(child, depth + 1, id)
  }
  walk(root, 0, null)

  const H_SPACING = 240
  const V_SPACING = 110
  const maxWidth = Math.max(...levels.map((l) => l.length))

  levels.forEach((level, depth) => {
    const totalWidth = (level.length - 1) * H_SPACING
    const offset = (maxWidth - 1) * H_SPACING / 2 - totalWidth / 2
    level.forEach(({ id, node, parentId }, i) => {
      const palette = nodeColor(node)
      const stake = node.stake_pct != null ? ` — ${node.stake_pct}%` : ''
      nodes.push({
        id,
        position: { x: i * H_SPACING + offset, y: depth * V_SPACING },
        data: {
          label: (
            <div style={{ fontSize: 11, lineHeight: 1.3 }}>
              <div style={{ fontWeight: 600 }}>{node.name}{stake}</div>
              <div style={{ opacity: 0.75, fontSize: 10 }}>
                {node.entity_type}
                {node.jurisdiction ? ` · ${node.jurisdiction}` : ''}
              </div>
              {node.note && (
                <div style={{ opacity: 0.65, fontSize: 10, fontStyle: 'italic', marginTop: 2 }}>
                  {node.note}
                </div>
              )}
            </div>
          ),
        },
        style: {
          background: palette.bg,
          border: `2px solid ${palette.border}`,
          borderRadius: 6,
          padding: 6,
          width: 200,
        },
        sourcePosition: 'bottom',
        targetPosition: 'top',
      })
      if (parentId) {
        edges.push({
          id: `e-${parentId}-${id}`,
          source: parentId,
          target: id,
          markerEnd: { type: MarkerType.ArrowClosed },
          type: 'smoothstep',
        })
      }
    })
  })

  // Height roughly scales with depth so the canvas isn't cramped
  const height = Math.max(300, levels.length * V_SPACING + 80)
  return { nodes, edges, height }
}

export default function UboGraphView({ root }) {
  const { nodes, edges, height } = useMemo(() => layoutTree(root), [root])

  return (
    <div style={{ height, border: '1px solid #e1e4e8', borderRadius: 6, background: '#fafbfc' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
