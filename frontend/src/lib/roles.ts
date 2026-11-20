import type { CatalystReport, Edge } from '../types/caif'

export type Role = 'HEAD' | 'TAIL' | 'CATALYST' | 'REQUIRED' | 'BLOCKED' | 'FUSION' | 'NONE'

export const ROLE_STYLE: Record<Role, { label: string; chip: string; node: string; hint: string }> = {
  HEAD: { label: 'HEAD', chip: 'bg-blue-100 text-blue-800 ring-blue-300', node: 'border-blue-500 bg-blue-50', hint: 'First memory operation of the candidate pair' },
  TAIL: { label: 'TAIL', chip: 'bg-violet-100 text-violet-800 ring-violet-300', node: 'border-violet-500 bg-violet-50', hint: 'Second memory operation; CAIF tries to move it next to the HEAD' },
  CATALYST: { label: 'CATALYST', chip: 'bg-amber-100 text-amber-800 ring-amber-300', node: 'border-amber-400 bg-amber-50', hint: 'Instruction between HEAD and TAIL that may stay where it is' },
  REQUIRED: { label: 'REQUIRED DEP.', chip: 'bg-cyan-100 text-cyan-800 ring-cyan-300', node: 'border-cyan-500 bg-cyan-50', hint: "In the TAIL's use-def chain: must be hoisted together with the TAIL" },
  BLOCKED: { label: 'BLOCKED', chip: 'bg-red-100 text-red-800 ring-red-300', node: 'border-red-500 bg-red-50', hint: 'Takes part in a dependence that forbids the move' },
  FUSION: { label: 'FUSION CANDIDATE', chip: 'bg-emerald-100 text-emerald-800 ring-emerald-300', node: 'border-emerald-500 bg-emerald-50', hint: 'Part of a consecutive compatible pair' },
  NONE: { label: '', chip: 'bg-slate-100 text-slate-600 ring-slate-200', node: 'border-slate-300 bg-slate-100', hint: '' },
}

/** Role of every instruction with respect to one candidate pair (and the set of formed pairs). */
export function computeRoles(report: CatalystReport | null, fused: Iterable<string> = []): Record<string, Role> {
  const roles: Record<string, Role> = {}
  for (const id of fused) roles[id] = 'FUSION'
  if (!report) return roles
  const blocked = new Set<string>()
  for (const v of report.violations) { blocked.add(v.src); blocked.add(v.dst) }
  for (const id of report.catalyst) roles[id] = 'CATALYST'
  for (const id of report.chain) roles[id] = 'REQUIRED'
  for (const id of blocked) if (id !== report.head && id !== report.tail) roles[id] = 'BLOCKED'
  roles[report.head] = 'HEAD'
  roles[report.tail] = 'TAIL'
  return roles
}

export const EDGE_COLOR: Record<string, string> = {
  RAW: '#60a5fa',
  ADDRESS: '#22d3ee',
  WAR: '#fbbf24',
  WAW: '#c084fc',
  MEMORY: '#f87171',
}

export function edgeLabel(e: Edge) {
  if (e.type === 'MEMORY') return e.subtype === 'CALL' ? 'MEMORY (call)' : `MEMORY ${e.subtype.replace('MEM-', '')}`
  return `${e.type} ${e.subtype}`
}
