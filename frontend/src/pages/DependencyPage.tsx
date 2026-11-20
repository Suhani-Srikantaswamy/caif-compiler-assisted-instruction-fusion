import { useMemo, useState } from 'react'
import { Card, Legend, NeedsRun, PageHeader } from '../components/ui'
import { DependencyGraph, edgeKey } from '../graphs/DependencyGraph'
import { EDGE_COLOR, computeRoles } from '../lib/roles'
import { pairKey, useApp } from '../state/AppState'

const TYPES = ['RAW', 'ADDRESS', 'WAR', 'WAW', 'MEMORY']

export default function DependencyPage() {
  return (
    <div>
      <PageHeader title="Dependency Visualization"
        subtitle="Each node is an instruction and each arrow is an ordering constraint (src must stay before dst). Rows follow program order; columns show dependence depth. Click a node to inspect it, and pick a candidate pair to colour its HEAD, TAIL and catalyst." />
      <NeedsRun><Body /></NeedsRun>
    </div>
  )
}

function Body() {
  const { result, selectedPair, setSelectedPair } = useApp()
  const r = result!
  const [mode, setMode] = useState<'original' | 'optimized'>('original')
  const [selected, setSelected] = useState<string | null>(null)
  const [visible, setVisible] = useState(new Set(TYPES))

  const compatible = r.candidates.filter((c) => c.compatible)
  // The original-program report matches the original-order graph shown here.
  const report = (selectedPair ? r.catalyst_reports[selectedPair] : undefined) ?? null
  const fused = mode === 'optimized' ? r.opportunities_after.flatMap((p) => [p.head, p.tail]) : r.opportunities_before.flatMap((p) => [p.head, p.tail])
  const roles = useMemo(() => computeRoles(mode === 'original' ? report : null, fused), [mode, report, fused])
  const violationKeys = useMemo(() => new Set(mode === 'original' && report ? report.violations.map(edgeKey) : []), [mode, report])

  const instructions = mode === 'original' ? r.instructions : r.optimized
  const edges = mode === 'original' ? r.graph.edges : r.optimized_graph.edges
  const sel = instructions.find((i) => i.id === selected)
  const preds = edges.filter((e) => e.dst === selected)
  const succs = edges.filter((e) => e.src === selected)

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
      <div className="space-y-4">
        <Card>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <div className="inline-flex rounded-lg border border-slate-300 p-0.5">
              {(['original', 'optimized'] as const).map((m) => (
                <button key={m} onClick={() => setMode(m)}
                  className={`rounded-md px-3 py-1 font-medium capitalize ${mode === m ? 'bg-indigo-500 text-white' : 'text-slate-600'}`}>{m}</button>
              ))}
            </div>
            <label className="flex items-center gap-2">
              Candidate pair
              <select className="rounded-md border border-slate-300 px-2 py-1" value={selectedPair ?? ''} onChange={(e) => setSelectedPair(e.target.value || null)} disabled={mode === 'optimized'}>
                <option value="">none</option>
                {compatible.map((c) => <option key={pairKey(c.head, c.tail)} value={pairKey(c.head, c.tail)}>{c.head} + {c.tail}{c.consecutive ? ' (consecutive)' : ''}</option>)}
              </select>
            </label>
            <div className="flex flex-wrap gap-3">
              {TYPES.map((t) => (
                <label key={t} className="flex items-center gap-1 text-xs font-semibold" style={{ color: EDGE_COLOR[t] }}>
                  <input type="checkbox" checked={visible.has(t)} onChange={(e) => {
                    const n = new Set(visible); if (e.target.checked) n.add(t); else n.delete(t); setVisible(n)
                  }} />{t}
                </label>
              ))}
            </div>
          </div>
          <div className="mt-3"><Legend roles={['HEAD', 'TAIL', 'CATALYST', 'REQUIRED', 'BLOCKED', 'FUSION']} /></div>
          {mode === 'original' && report && (
            <p className={`mt-2 text-xs ${report.safe ? 'text-emerald-700' : 'text-red-700'}`}>
              {report.safe ? `Pair ${report.head}+${report.tail}: no blocking edge, so the move is safe.` : `Pair ${report.head}+${report.tail}: animated red edges block the move.`}
            </p>
          )}
          {mode === 'optimized' && <p className="mt-2 text-xs text-slate-500">Optimized order. Green nodes are consecutive fusion opportunities, and "moved from #k" marks instructions that changed position.</p>}
        </Card>
        <DependencyGraph instructions={instructions} edges={edges} roles={roles} selected={selected} onSelect={setSelected}
          visibleTypes={visible} violationKeys={violationKeys} />
      </div>

      <Card title="Inspector">
        {!sel ? <p className="text-sm text-slate-500">Click an instruction node to see its dependences.</p> : (
          <div className="space-y-3 text-sm">
            <div>
              <div className="mono text-base font-semibold">{sel.id}: {sel.text}</div>
              <div className="text-xs text-slate-500">{sel.explanation}</div>
              <div className="mt-1 text-xs text-slate-500">block {sel.block}, position {sel.position}{sel.original_position !== undefined ? ` (originally ${sel.original_position})` : ''}</div>
              {sel.mem && r.memory[sel.id] && <div className="mt-1 text-xs">address <span className="mono">{r.memory[sel.id].address}</span>, {sel.mem.size} B</div>}
            </div>
            <EdgeList title={`Must come after (${preds.length})`} edges={preds} other={(e) => e.src} />
            <EdgeList title={`Must come before (${succs.length})`} edges={succs} other={(e) => e.dst} />
          </div>
        )}
      </Card>
    </div>
  )
}

function EdgeList({ title, edges, other }: { title: string; edges: { src: string; dst: string; type: string; subtype: string; reason: string }[]; other: (e: { src: string; dst: string }) => string }) {
  return (
    <div>
      <div className="mb-1 text-xs font-semibold uppercase text-slate-500">{title}</div>
      {edges.length === 0 ? <div className="text-xs text-slate-400">none</div> : (
        <ul className="space-y-1">
          {edges.map((e, i) => (
            <li key={i} className="rounded bg-slate-50 px-2 py-1 text-xs">
              <span className="mono font-semibold">{other(e)}</span>{' '}
              <span className="font-semibold" style={{ color: EDGE_COLOR[e.type] }}>{e.type}{e.subtype ? `/${e.subtype}` : ''}</span>
              <div className="text-slate-500">{e.reason}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
