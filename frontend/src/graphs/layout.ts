import type { Edge } from '../types/caif'

export interface Pos { x: number; y: number; depth: number }

/**
 * Layered layout: y = program position, x = dependence depth (longest path
 * from a root). Independent instructions share the left column, so the
 * critical dependence chains are visible as diagonals.
 */
export function layoutGraph(order: string[], edges: Edge[], colW = 230, rowH = 74): Record<string, Pos> {
  const pos: Record<string, number> = Object.fromEntries(order.map((id, i) => [id, i]))
  const depth: Record<string, number> = Object.fromEntries(order.map((id) => [id, 0]))
  const preds: Record<string, string[]> = {}
  for (const e of edges) (preds[e.dst] ??= []).push(e.src)
  for (const id of order) {
    for (const p of preds[id] ?? []) {
      if (pos[p] !== undefined && pos[p] < pos[id]) depth[id] = Math.max(depth[id], depth[p] + 1)
    }
  }
  const out: Record<string, Pos> = {}
  order.forEach((id, i) => { out[id] = { x: depth[id] * colW, y: i * rowH, depth: depth[id] } })
  return out
}
