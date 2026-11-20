import { useMemo } from 'react'
import {
  Background, Controls, Handle, MarkerType, Position, ReactFlow,
  type Edge as RFEdge, type Node as RFNode, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { EDGE_COLOR, ROLE_STYLE, edgeLabel, type Role } from '../lib/roles'
import type { Edge, Instruction } from '../types/caif'
import { layoutGraph } from './layout'

type InsNodeData = { ins: Instruction; role: Role; selected: boolean; dim: boolean; movedFrom?: number }

function InsNode({ data }: NodeProps<RFNode<InsNodeData>>) {
  const { ins, role, selected, dim, movedFrom } = data
  return (
    <div className={`w-[200px] rounded-lg border-2 px-2.5 py-1.5 shadow-sm transition ${ROLE_STYLE[role].node} ${selected ? 'ring-2 ring-indigo-500 ring-offset-1 ring-offset-slate-50' : ''} ${dim ? 'opacity-35' : ''}`}>
      <Handle type="target" position={Position.Top} className="!h-1.5 !w-1.5 !bg-slate-400" />
      <div className="flex items-center justify-between gap-1">
        <span className="font-mono text-[11px] font-bold">{ins.id}<span className="ml-1 font-normal text-slate-400">#{ins.position}</span></span>
        {role !== 'NONE' && <span className={`rounded px-1 text-[9px] font-semibold ring-1 ring-inset ${ROLE_STYLE[role].chip}`}>{ROLE_STYLE[role].label}</span>}
      </div>
      <div className="truncate font-mono text-[11px] text-slate-700" title={ins.text}>{ins.text}</div>
      {movedFrom !== undefined && movedFrom !== ins.position && <div className="text-[9px] text-orange-600">moved from #{movedFrom}</div>}
      <Handle type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !bg-slate-400" />
    </div>
  )
}

const nodeTypes = { ins: InsNode }

export interface DependencyGraphProps {
  instructions: Instruction[]
  edges: Edge[]
  roles: Record<string, Role>
  selected: string | null
  onSelect: (id: string | null) => void
  visibleTypes: Set<string>
  violationKeys?: Set<string>
}

export function edgeKey(e: Edge) { return `${e.src}->${e.dst}:${e.type}:${e.subtype}` }

export function DependencyGraph({ instructions, edges, roles, selected, onSelect, visibleTypes, violationKeys }: DependencyGraphProps) {
  const { nodes, rfEdges } = useMemo(() => {
    const shown = edges.filter((e) => visibleTypes.has(e.type))
    const pos = layoutGraph(instructions.map((i) => i.id), shown)
    const neighbours = new Set<string>()
    if (selected) {
      neighbours.add(selected)
      for (const e of shown) if (e.src === selected || e.dst === selected) { neighbours.add(e.src); neighbours.add(e.dst) }
    }
    const nodes: RFNode<InsNodeData>[] = instructions.map((ins) => ({
      id: ins.id, type: 'ins', position: { x: pos[ins.id].x, y: pos[ins.id].y },
      data: { ins, role: roles[ins.id] ?? 'NONE', selected: ins.id === selected, dim: !!selected && !neighbours.has(ins.id), movedFrom: ins.original_position },
    }))
    const rfEdges: RFEdge[] = shown.map((e) => {
      const viol = violationKeys?.has(edgeKey(e))
      const touches = !selected || e.src === selected || e.dst === selected
      const color = viol ? '#ef4444' : EDGE_COLOR[e.type] ?? '#94a3b8'
      return {
        id: edgeKey(e), source: e.src, target: e.dst, label: edgeLabel(e),
        animated: !!viol,
        style: { stroke: color, strokeWidth: viol ? 3 : 1.6, opacity: touches ? 1 : 0.15, strokeDasharray: e.type === 'MEMORY' ? '5 3' : undefined },
        labelStyle: { fontSize: 10, fill: color, fontWeight: 600 },
        labelBgStyle: { fill: '#0f172a', fillOpacity: touches ? 0.9 : 0.2 },
        markerEnd: { type: MarkerType.ArrowClosed, color },
      }
    })
    return { nodes, rfEdges }
  }, [instructions, edges, roles, selected, visibleTypes, violationKeys])

  return (
    <div className="h-[560px] w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-50" data-testid="dep-graph">
      <ReactFlow colorMode="dark" nodes={nodes} edges={rfEdges} nodeTypes={nodeTypes} fitView minZoom={0.2}
        nodesDraggable nodesConnectable={false} elementsSelectable
        onNodeClick={(_, n) => onSelect(n.id === selected ? null : n.id)} onPaneClick={() => onSelect(null)}
        proOptions={{ hideAttribution: false }}>
        <Background gap={18} color="#1e293b" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
