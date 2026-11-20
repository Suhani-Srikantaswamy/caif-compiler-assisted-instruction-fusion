import { useCallback, useEffect, useState } from 'react'
import { GroupedBars } from '../charts/Charts'
import { Card, PageHeader, Stat } from '../components/ui'
import { PAPER_FACTS, PAPER_NN_EXEC } from '../data/paperResults'
import { api, ApiError } from '../services/api'
import { useApp } from '../state/AppState'
import type { ExperimentRun, ExperimentSummary } from '../types/caif'

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click()
  URL.revokeObjectURL(url)
}

const CSV_COLS = ['sample_id', 'target', 'instructions', 'memory_instructions', 'candidate_pairs', 'dependencies',
  'rearrangements_attempted', 'successful_rearrangements', 'rejected_rearrangements', 'consecutive_before',
  'consecutive_after', 'additional_opportunities', 'percent_increase', 'optimizer_time_ms', 'validation_passed', 'matches_specification'] as const

export default function ResultsPage() {
  const { result } = useApp()
  const [runs, setRuns] = useState<ExperimentSummary[]>([])
  const [run, setRun] = useState<ExperimentRun | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [label, setLabel] = useState('')

  const refresh = useCallback(async (selectId?: string) => {
    const list = await api.experiments()
    setRuns(list)
    const id = selectId ?? list[0]?.id
    if (id) setRun(await api.experiment(id))
  }, [])

  useEffect(() => { refresh().catch((e) => setErr(String(e))) }, [refresh])

  const runSuite = async () => {
    setBusy(true); setErr(null)
    try {
      const r = await api.runExperiments(label)
      await refresh(r.id)
    } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)) } finally { setBusy(false) }
  }

  const m = result?.metrics
  const short = (id: string) => id.replace(/^s(\d+)_.*/, 'S$1')

  return (
    <div className="space-y-8">
      <PageHeader title="Results and Experiments"
        subtitle="Local results come from running this implementation. Paper-reported results are in a separate section at the bottom and are never combined with local ones." />

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">A. Current program (local)</h2>
        {!m ? <p className="text-sm text-slate-500">Run CAIF on the Instruction Input page to see metrics for the current program.</p> : (
          <>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Stat label="Consecutive before" value={m.consecutive_before} />
              <Stat label="Consecutive after" value={m.consecutive_after} tone="indigo" />
              <Stat label="Additional" value={`+${m.additional_opportunities}`} tone="green" />
              <Stat label="% change" value={m.percent_increase === null ? 'n/a' : `${m.percent_increase}%`} hint={m.percent_increase === null ? 'undefined: before = 0' : undefined} />
              <Stat label="Successful moves" value={m.successful_rearrangements} tone="green" />
              <Stat label="Rejected moves" value={m.rejected_rearrangements} tone={m.rejected_rearrangements ? 'red' : 'slate'} />
            </div>
            <p className="text-xs text-slate-500">{m.note} Optimizer time for this run: {m.optimizer_time_ms} ms (compile-time cost of the Python optimizer).</p>
          </>
        )}
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-lg font-semibold">B. Experiment suite: all predefined samples (local)</h2>
          <div className="flex flex-wrap items-center gap-2">
            <input className="rounded-md border border-slate-300 px-2 py-1.5 text-sm" placeholder="label (optional)" value={label} onChange={(e) => setLabel(e.target.value)} />
            <button className="btn-primary" disabled={busy} onClick={runSuite}>{busy ? 'Running...' : 'Run experiment suite'}</button>
            {runs.length > 0 && (
              <select aria-label="Experiment history" className="rounded-md border border-slate-300 px-2 py-1.5 text-sm" value={run?.id ?? ''}
                onChange={(e) => api.experiment(e.target.value).then(setRun)}>
                {runs.map((r) => <option key={r.id} value={r.id}>{r.id}{r.label ? ` (${r.label})` : ''}</option>)}
              </select>
            )}
          </div>
        </div>
        {err && <p className="text-sm text-red-700">{err}</p>}
        {!run ? <p className="text-sm text-slate-500">No experiment has been run yet. Press <b>Run experiment suite</b>.</p> : <RunView run={run} short={short} />}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">C. Results reported in the paper (not produced by this project)</h2>
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          Reported by Reddy et al. (CGO 2026) from their LLVM implementation, measured in a cycle-level RISC-V simulator of a
          Gracemont-like core. Shown here only for context. They are not comparable with the local opportunity counts above.
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Paper: average execution-time reduction on NN kernels vs NoFusion-Base (%)">
            <GroupedBars data={PAPER_NN_EXEC} xKey="config" yLabel="% reduction"
              series={[{ key: 'base', name: 'Base compiler (-O3)' }, { key: 'caif', name: 'CAIF' }]} />
            <table className="tbl mt-2"><thead><tr><th>Hardware</th><th>Base</th><th>CAIF</th></tr></thead>
              <tbody>{PAPER_NN_EXEC.map((r) => <tr key={r.config}><td>{r.config}</td><td>{r.base}%</td><td>{r.caif}%</td></tr>)}</tbody></table>
            <p className="mt-2 text-xs text-slate-500">Source: Sec. VI-D / Fig. 9.</p>
          </Card>
          <Card title="Paper: other reported figures">
            <table className="tbl"><thead><tr><th>Metric</th><th>Reported value</th><th>Where</th></tr></thead>
              <tbody>{PAPER_FACTS.map((f) => <tr key={f.metric}><td className="text-xs">{f.metric}</td><td className="text-xs font-medium">{f.value}</td><td className="text-xs text-slate-500">{f.source}</td></tr>)}</tbody></table>
          </Card>
        </div>
      </section>
    </div>
  )
}

function RunView({ run, short }: { run: ExperimentRun; short: (id: string) => string }) {
  const rows = run.rows.map((r) => ({ ...r, name: short(r.sample_id) }))
  const t = run.totals
  const csv = [CSV_COLS.join(','), ...run.rows.map((r) => CSV_COLS.map((c) => String(r[c] ?? '')).join(','))].join('\n')
  const sweep = ['ConsSBR', 'ConsSBR64', 'Cons'].map((target) => {
    const o: Record<string, unknown> = { target }
    for (const s of run.sweep.filter((x) => x.target === target)) o[`w${s.window_bytes}`] = s.consecutive_after
    return o
  })
  const windows = [...new Set(run.sweep.map((s) => s.window_bytes))]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span>Run <span className="mono">{run.id}</span>, created {run.created}.{run.files && <> Saved to <span className="mono">{run.files.json}</span> and <span className="mono">{run.files.csv}</span>.</>}</span>
        <button className="btn-secondary !py-1" onClick={() => download(`${run.id}.json`, JSON.stringify(run, null, 2), 'application/json')}>Download JSON</button>
        <button className="btn-secondary !py-1" onClick={() => download(`${run.id}.csv`, csv, 'text/csv')}>Download CSV</button>
        <button className="btn-secondary !py-1" onClick={() => api.report(run.id).then((r) => download(`${run.id}.md`, r.markdown, 'text/markdown'))}>Download report (.md)</button>
      </div>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Samples" value={run.rows.length} />
        <Stat label="Opportunities before" value={String(t.consecutive_before)} />
        <Stat label="Opportunities after" value={String(t.consecutive_after)} tone="indigo" />
        <Stat label="Successful / rejected" value={`${t.successful_rearrangements} / ${t.rejected_rearrangements}`} />
        <Stat label="All validated" value={t.all_valid ? 'yes' : 'NO'} tone={t.all_valid ? 'green' : 'red'} />
        <Stat label="All match spec" value={t.all_match_specification ? 'yes' : 'NO'} tone={t.all_match_specification ? 'green' : 'red'} />
      </div>
      <p className="text-xs text-slate-500">{run.note}</p>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Consecutive fusion opportunities per sample">
          <GroupedBars data={rows} xKey="name" yLabel="pairs"
            series={[{ key: 'consecutive_before', name: 'Before CAIF' }, { key: 'consecutive_after', name: 'After CAIF' }]} />
        </Card>
        <Card title="Rearrangement decisions per sample">
          <GroupedBars data={rows} xKey="name" yLabel="attempts" stacked
            series={[{ key: 'successful_rearrangements', name: 'Successful' }, { key: 'rejected_rearrangements', name: 'Rejected' }]} />
        </Card>
        <Card title="Sensitivity: opportunities after CAIF, by target model and window size (all samples)">
          <GroupedBars data={sweep} xKey="target" yLabel="pairs"
            series={windows.map((w) => ({ key: `w${w}`, name: `${w} B window` }))} />
          <p className="mt-1 text-xs text-slate-500">Before CAIF there are {run.sweep[0]?.consecutive_before ?? 0} opportunities in every configuration.</p>
        </Card>
        <Card title="Optimizer compile-time cost per sample (median ms, Python)">
          <GroupedBars data={rows} xKey="name" yLabel="ms" series={[{ key: 'optimizer_time_ms', name: 'Optimizer time (ms)' }]} />
          <p className="mt-1 text-xs text-slate-500">Wall-clock time of the analysis and reordering algorithm, not program execution time.</p>
        </Card>
      </div>

      <Card title="Per-sample table">
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead><tr>
              <th>Sample</th><th>Target</th><th>Instr</th><th>Mem</th><th>Cand.</th><th>Deps</th><th>Attempted</th><th>OK</th><th>Rejected</th>
              <th>Before</th><th>After</th><th>+</th><th>%</th><th>ms</th><th>Valid</th><th>Spec</th>
            </tr></thead>
            <tbody>
              {run.rows.map((r) => (
                <tr key={r.sample_id}>
                  <td className="text-xs">{r.title}</td><td className="text-xs">{r.target}</td>
                  <td>{r.instructions}</td><td>{r.memory_instructions}</td><td>{r.candidate_pairs}</td><td>{r.dependencies}</td>
                  <td>{r.rearrangements_attempted}</td><td>{r.successful_rearrangements}</td><td>{r.rejected_rearrangements}</td>
                  <td>{r.consecutive_before}</td><td>{r.consecutive_after}</td><td>{r.additional_opportunities}</td>
                  <td>{r.percent_increase ?? 'n/a'}</td><td className="tabular-nums">{r.optimizer_time_ms}</td>
                  <td>{r.validation_passed ? '✓' : '✗'}</td><td>{r.matches_specification ? '✓' : '✗'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Observations (derived from this run)">
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>Across {run.rows.length} samples, consecutive opportunities went from {String(t.consecutive_before)} to {String(t.consecutive_after)}; the share of memory instructions in a consecutive pair went from {String(t.fused_memory_ops_before_pct)}% to {String(t.fused_memory_ops_after_pct)}%.</li>
          <li>{String(t.rejected_rearrangements)} candidate move(s) were rejected. Every one is explained by a concrete dependence:</li>
        </ul>
        <ul className="ml-10 mt-1 list-[circle] space-y-1 text-xs text-slate-500">
          {run.rows.flatMap((r) => r.rejection_reasons.map((x, i) => <li key={r.sample_id + i}><b>{short(r.sample_id)}</b>: {x.replace(/^Rejected: /, '')}</li>))}
        </ul>
      </Card>
    </div>
  )
}
