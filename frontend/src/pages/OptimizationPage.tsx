import { useState } from 'react'
import { Card, NeedsRun, PageHeader, Pill, RoleChip, StatusBanner } from '../components/ui'
import { useApp } from '../state/AppState'
import type { Instruction, OptimizeResponse, Step } from '../types/caif'

export default function OptimizationPage() {
  return (
    <div>
      <PageHeader title="Optimization Visualization"
        subtitle="The original and optimized instruction sequences side by side, followed by every decision the optimizer made, step by step." />
      <NeedsRun><Body /></NeedsRun>
    </div>
  )
}

function Body() {
  const { result } = useApp()
  const r = result!
  const newPairs = new Set(r.opportunities_after.map((p) => `${p.head}-${p.tail}`))
  const oldPairs = new Set(r.opportunities_before.map((p) => `${p.head}-${p.tail}`))
  const moved = new Set(r.metrics.instructions_moved)
  const headIds = new Set(r.pairs.map((p) => p[0]))
  const tailIds = new Set(r.pairs.map((p) => p[1]))
  const catalystIds = new Set(r.steps.filter((s) => s.action === 'REARRANGED').flatMap((s) => s.catalyst?.catalyst ?? []))

  return (
    <div className="space-y-6">
      <StatusBanner />
      <div className="flex flex-wrap gap-2 text-xs">
        <RoleChip role="HEAD" /> <RoleChip role="TAIL" /> <RoleChip role="CATALYST" />
        <span className="rounded-md bg-orange-100 px-1.5 py-0.5 font-semibold text-orange-800 ring-1 ring-inset ring-orange-300">MOVED</span>
        <span className="rounded-md bg-emerald-100 px-1.5 py-0.5 font-semibold text-emerald-800 ring-1 ring-inset ring-emerald-300">NEW CONSECUTIVE PAIR</span>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <SeqCard title={`Original (${r.metrics.consecutive_before} consecutive pair${r.metrics.consecutive_before === 1 ? '' : 's'})`}
          seq={r.instructions} pairs={oldPairs} isNew={() => false} moved={new Set()} heads={headIds} tails={tailIds} catalyst={catalystIds} />
        <SeqCard title={`Optimized (${r.metrics.consecutive_after} consecutive pair${r.metrics.consecutive_after === 1 ? '' : 's'})`}
          seq={r.optimized} pairs={newPairs} isNew={(k) => !oldPairs.has(k)} moved={moved} heads={headIds} tails={tailIds} catalyst={catalystIds} />
      </div>

      <Card title="Validation (re-checked from the original program, not trusted from the optimizer)">
        <ul className="space-y-1.5 text-sm">
          {r.validation.checks.map((c) => (
            <li key={c.name} className="flex gap-2"><span className={c.passed ? 'text-emerald-600' : 'text-red-600'}>{c.passed ? '✓' : '✗'}</span>
              <span><span className="mono text-xs text-slate-500">{c.name}</span> {c.details}</span></li>
          ))}
        </ul>
        {!r.validation.valid && <p className="mt-2 text-sm font-semibold text-red-700">Validation failed, so the original sequence was kept.</p>}
        <p className="mt-3 text-xs text-slate-500">
          The static check (<span className="mono">dependences_preserved</span>) uses a different rule from the optimizer
          (every reordered pair must commute) but the <i>same</i> alias analysis. The differential execution check is fully
          independent: it runs both programs in an interpreter under many aliasing set-ups. Both are evidence under the model,
          not a formal proof.
        </p>
      </Card>

      <Stepper r={r} />
    </div>
  )
}

function SeqCard({ title, seq, pairs, isNew, moved, heads, tails, catalyst }: {
  title: string; seq: Instruction[]; pairs: Set<string>; isNew: (k: string) => boolean
  moved: Set<string>; heads: Set<string>; tails: Set<string>; catalyst: Set<string>
}) {
  return (
    <Card title={title}>
      <ol className="space-y-1">
        {seq.map((ins, k) => {
          const next = seq[k + 1]
          const prev = seq[k - 1]
          const startsPair = next && pairs.has(`${ins.id}-${next.id}`)
          const endsPair = prev && pairs.has(`${prev.id}-${ins.id}`)
          const inPair = startsPair || endsPair
          const pairNew = startsPair ? isNew(`${ins.id}-${next.id}`) : endsPair ? isNew(`${prev.id}-${ins.id}`) : false
          const wasMoved = moved.has(ins.id)
          return (
            <li key={ins.id} className={`flex items-center gap-2 rounded-md border px-2 py-1.5 text-sm
              ${inPair ? (pairNew ? 'border-emerald-400 bg-emerald-50' : 'border-emerald-200 bg-emerald-50/50') : 'border-slate-200 bg-slate-100'}
              ${wasMoved ? 'border-l-4 !border-l-orange-500' : ''}`}>
              <span className="w-6 text-right text-xs tabular-nums text-slate-400">{k}</span>
              <span className="mono w-10 font-semibold">{ins.id}</span>
              <span className="mono flex-1">{ins.text}</span>
              <span className="flex flex-wrap justify-end gap-1">
                {heads.has(ins.id) && inPair && <RoleChip role="HEAD" />}
                {tails.has(ins.id) && inPair && <RoleChip role="TAIL" />}
                {catalyst.has(ins.id) && !wasMoved && <RoleChip role="CATALYST" />}
                {wasMoved && <span className="rounded bg-orange-100 px-1 text-[10px] font-semibold text-orange-800">MOVED{ins.original_position !== undefined ? ` from #${ins.original_position}` : ''}</span>}
                <span className="text-[10px] text-slate-400">{ins.block}</span>
              </span>
            </li>
          )
        })}
      </ol>
    </Card>
  )
}

function Stepper({ r }: { r: OptimizeResponse }) {
  const [i, setI] = useState(0)
  if (!r.steps.length) {
    return <Card title="Step-by-step explanation"><p className="text-sm text-slate-500">The optimizer found no compatible candidate pair, so there were no decisions to make.</p></Card>
  }
  const s: Step = r.steps[Math.min(i, r.steps.length - 1)]
  const byId = Object.fromEntries(r.instructions.map((x) => [x.id, x]))
  const movedSet = new Set(s.moved)
  return (
    <Card title={`Step-by-step explanation (${r.steps.length} decision${r.steps.length === 1 ? '' : 's'})`} right={
      <div className="flex items-center gap-2 font-normal">
        <button className="btn-secondary !py-1" disabled={i === 0} onClick={() => setI(i - 1)}>← Prev</button>
        <span className="text-xs tabular-nums">{i + 1} / {r.steps.length}</span>
        <button className="btn-secondary !py-1" disabled={i >= r.steps.length - 1} onClick={() => setI(i + 1)}>Next →</button>
      </div>
    }>
      <div className="mb-3 flex items-center gap-2">
        <Pill ok={s.action === 'REJECTED' ? false : true}>Step {s.number}: {s.action}</Pill>
        <span className="mono text-sm">{s.head} + {s.tail}</span>
      </div>
      <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm text-slate-700">
        {s.explanation.map((e, k) => <li key={k} className={e.startsWith('Rejected') ? 'text-red-700' : ''}>{e}</li>)}
      </ol>
      <div className="grid gap-4 md:grid-cols-2">
        {[['Before this step', s.before], ['After this step', s.after]].map(([label, ids]) => (
          <div key={label as string}>
            <div className="mb-1 text-xs font-semibold uppercase text-slate-500">{label as string}</div>
            <ol className="space-y-0.5">
              {(ids as string[]).map((id) => {
                const role = id === s.head ? 'HEAD' : id === s.tail ? 'TAIL' : s.catalyst?.chain.includes(id) ? 'REQUIRED' : s.catalyst?.catalyst.includes(id) ? 'CATALYST' : null
                return (
                  <li key={id} className={`mono flex items-center gap-2 rounded px-2 py-0.5 text-xs ${label === 'After this step' && movedSet.has(id) ? 'bg-orange-50' : ''}`}>
                    <span className="w-8 font-semibold">{id}</span><span className="flex-1 text-slate-600">{byId[id]?.text}</span>
                    {role && <RoleChip role={role} />}
                  </li>
                )
              })}
            </ol>
          </div>
        ))}
      </div>
    </Card>
  )
}
