import { useState } from 'react'
import { Card, NeedsRun, PageHeader, Pill, RoleChip, StatusBanner } from '../components/ui'
import { pairKey, useApp } from '../state/AppState'
import type { Candidate, CatalystReport, OptimizeResponse } from '../types/caif'

export default function FusionAnalysis() {
  return (
    <div>
      <PageHeader title="Fusion Analysis"
        subtitle="Stage 3 finds same-kind memory pairs and checks every compatibility condition. For compatible but non-consecutive pairs, Stages 4-5 analyse the catalyst and decide whether the TAIL can safely be moved." />
      <NeedsRun><Body /></NeedsRun>
    </div>
  )
}

function Body() {
  const { result, selectedPair, setSelectedPair } = useApp()
  const [showAll, setShowAll] = useState(false)
  const r = result!
  const shown = r.candidates.filter((c) => showAll || c.compatible)
  const sel = r.candidates.find((c) => pairKey(c.head, c.tail) === selectedPair) ?? null

  return (
    <div className="space-y-6">
      <StatusBanner />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Mini label="Memory instructions" v={r.metrics.memory_instructions} />
        <Mini label="Compatible pairs" v={r.metrics.compatible_candidate_pairs} />
        <Mini label="Non-consecutive (worth rearranging)" v={r.metrics.non_consecutive_candidate_pairs} />
        <Mini label="Dependences" v={`${r.metrics.dependencies} (${Object.entries(r.graph.counts).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'})`} />
      </div>

      <Card title="Candidate memory instruction pairs" right={
        <label className="flex items-center gap-2 text-xs font-normal">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> show incompatible pairs too
        </label>
      }>
        {shown.length === 0 ? <p className="text-sm text-slate-500">No {showAll ? '' : 'compatible '}LOAD+LOAD or STORE+STORE pairs in the same basic block.</p> : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr>
                <th>HEAD</th><th>TAIL</th><th>Positions</th><th>Addresses</th><th>Sizes</th><th>Byte dist.</th><th>Instr. dist.</th>
                <th>Compatible</th><th>Consecutive</th><th>Rearrange useful?</th><th>Optimizer outcome</th>
              </tr></thead>
              <tbody>
                {shown.map((c) => {
                  const k = pairKey(c.head, c.tail)
                  const out = outcome(r, c)
                  return (
                    <tr key={k} onClick={() => setSelectedPair(k)}
                      className={`cursor-pointer hover:bg-indigo-50/50 ${selectedPair === k ? 'bg-indigo-50' : ''}`}>
                      <td className="mono"><b>{c.head}</b> <span className="text-slate-500">{c.head_text}</span></td>
                      <td className="mono"><b>{c.tail}</b> <span className="text-slate-500">{c.tail_text}</span></td>
                      <td className="tabular-nums">{c.head_pos} → {c.tail_pos}</td>
                      <td className="mono text-xs">{c.head_mem?.address} / {c.tail_mem?.address}</td>
                      <td className="text-xs">{c.head_mem?.size} B / {c.tail_mem?.size} B</td>
                      <td className="tabular-nums">{c.byte_distance ?? '?'}</td>
                      <td className="tabular-nums">{c.instruction_distance}</td>
                      <td><Pill ok={c.compatible}>{c.compatible ? c.fusion_class : 'no'}</Pill></td>
                      <td>{c.consecutive ? 'yes' : 'no'}</td>
                      <td>{c.rearrangement_useful ? 'yes' : '-'}</td>
                      <td className="text-xs">{out}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {sel ? <PairDetail r={r} c={sel} /> : <p className="text-sm text-slate-500">Select a pair to inspect it.</p>}
    </div>
  )
}

function Mini({ label, v }: { label: string; v: React.ReactNode }) {
  return <div className="card px-4 py-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 text-lg font-semibold">{v}</div></div>
}

function outcome(r: OptimizeResponse, c: Candidate) {
  const steps = r.steps.filter((s) => s.head === c.head && s.tail === c.tail)
  if (!c.compatible) return <span className="text-slate-400">not a candidate</span>
  if (steps.some((s) => s.action === 'REARRANGED')) return <span className="font-medium text-emerald-700">rearranged</span>
  if (steps.some((s) => s.action === 'CONSECUTIVE')) return <span className="text-emerald-700">already consecutive</span>
  if (steps.some((s) => s.action === 'REJECTED')) return <span className="font-medium text-red-700">rejected</span>
  const paired = r.pairs.find((p) => p.includes(c.head) || p.includes(c.tail))
  return <span className="text-slate-500">{paired ? `not tried (${paired.join('+')} formed instead)` : 'not tried'}</span>
}

function PairDetail({ r, c }: { r: OptimizeResponse; c: Candidate }) {
  const key = pairKey(c.head, c.tail)
  const steps = r.steps.filter((s) => s.head === c.head && s.tail === c.tail)
  const decisive = steps.find((s) => s.catalyst)
  // Prefer the report the optimizer actually used (it may run on a sequence already changed by earlier steps).
  const rep: CatalystReport | undefined = decisive?.catalyst ?? r.catalyst_reports[key]
  const changedContext = decisive && decisive.before.join() !== r.instructions.map((i) => i.id).join()
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title={<>Compatibility of <span className="mono">{c.head}</span> + <span className="mono">{c.tail}</span></>}>
        <div className="mb-4 grid grid-cols-2 gap-3 text-sm">
          {[['HEAD', c.head, c.head_text, c.head_mem], ['TAIL', c.tail, c.tail_text, c.tail_mem]].map(([role, id, text, m]) => (
            <div key={role as string} className="rounded-lg bg-slate-50 p-3">
              <RoleChip role={role as 'HEAD' | 'TAIL'} />
              <div className="mono mt-1 font-semibold">{id as string}: {text as string}</div>
              {m && typeof m === 'object' && (
                <div className="mt-1 text-xs text-slate-500">
                  resolved address <span className="mono">{m.address}</span>, {m.size} B ({m.kind}) <br /> base key <span className="mono">{m.base_key}</span>
                </div>
              )}
            </div>
          ))}
        </div>
        <ul className="space-y-1.5 text-sm">
          {c.conditions.map((cond) => (
            <li key={cond.name} className="flex gap-2">
              <span className={cond.passed ? 'text-emerald-600' : 'text-red-600'}>{cond.passed ? '✓' : '✗'}</span>
              <span><span className="mono text-xs text-slate-500">{cond.name}</span> {cond.detail}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={`Catalyst and dependence analysis${changedContext ? ` (as seen at step ${decisive!.number})` : ''}`}>
        {!c.compatible ? <p className="text-sm text-slate-500">The pair is not compatible, so no movement is considered.</p>
          : c.consecutive ? <p className="text-sm text-slate-500">The pair is already consecutive. There is no catalyst and nothing to move.</p>
            : rep ? <CatalystView rep={rep} /> : <p className="text-sm text-slate-500">No catalyst report.</p>}
        {steps.length > 0 && (
          <div className="mt-4 border-t border-slate-100 pt-3">
            <div className="mb-1 text-xs font-semibold uppercase text-slate-500">Optimizer log for this pair</div>
            {steps.map((s) => (
              <div key={s.number} className="mb-2 text-sm">
                <Pill ok={s.action !== 'REJECTED'}>Step {s.number}: {s.action}</Pill>
                <ul className="mt-1 list-disc pl-5 text-xs text-slate-600">{s.explanation.map((e, i) => <li key={i}>{e}</li>)}</ul>
                {s.catalyst && changedContext && (
                  <p className="text-xs text-slate-400">(attempted on the sequence produced by earlier steps: <span className="mono">{s.before.join(' ')}</span>)</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

export function CatalystView({ rep }: { rep: CatalystReport }) {
  return (
    <div className="space-y-3 text-sm">
      <div>Catalyst: {rep.catalyst.length ? rep.catalyst.map((x) => <span key={x} className="mono mr-1 rounded bg-amber-100 px-1">{x}</span>) : 'none'}</div>
      <div>Use-def chain of TAIL (moves with it): {rep.chain.length ? rep.chain.map((x) => <span key={x} className="mono mr-1 rounded bg-cyan-100 px-1">{x}</span>) : 'empty'}</div>
      <div className="overflow-x-auto">
        <table className="tbl">
          <thead><tr><th>Instr.</th><th>Depends on HEAD</th><th>TAIL needs it</th><th>Provides</th><th>Memory</th><th>Action</th><th>Blocks?</th></tr></thead>
          <tbody>
            {rep.entries.map((e) => (
              <tr key={e.id}>
                <td className="mono"><b>{e.id}</b> <span className="text-slate-500">{e.text}</span></td>
                <td>{e.depends_on_head ? 'yes' : 'no'}</td>
                <td>{e.in_tail_chain ? 'yes' : 'no'}</td>
                <td className="text-xs">{e.provides ?? '-'}</td>
                <td className="text-xs">{e.memory_effect}</td>
                <td className="text-xs">{e.action === 'MOVES_WITH_TAIL' ? <RoleChip role="REQUIRED">MOVES WITH TAIL</RoleChip> : e.can_remain ? 'stays (safe)' : 'stays'}</td>
                <td className="text-xs">{e.blocking.length ? <span className="text-red-700">{e.blocking.join('; ')}</span> : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={`rounded-lg p-3 ${rep.safe ? 'bg-emerald-50 text-emerald-900' : 'bg-red-50 text-red-900'}`}>
        <div className="font-semibold">{rep.safe ? 'Safe to rearrange' : 'Rearrangement rejected'}</div>
        {rep.safe ? <div className="mono mt-1 text-xs">new window order: {rep.proposed_order.join('  ')}</div>
          : <ul className="mt-1 list-disc pl-5 text-xs">{rep.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>}
      </div>
    </div>
  )
}
