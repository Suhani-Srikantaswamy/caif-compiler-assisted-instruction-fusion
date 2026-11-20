import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ROLE_STYLE, type Role } from '../lib/roles'
import { useApp } from '../state/AppState'

export function Card({ title, right, children, className = '' }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="card-h flex items-center justify-between gap-3">
          <span>{title}</span>
          {right}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}

export function RoleChip({ role, children }: { role: Role; children?: ReactNode }) {
  if (role === 'NONE' && !children) return null
  return (
    <span title={ROLE_STYLE[role].hint} className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ring-1 ring-inset ${ROLE_STYLE[role].chip}`}>
      {children ?? ROLE_STYLE[role].label}
    </span>
  )
}

export function Pill({ ok, children }: { ok: boolean | null; children: ReactNode }) {
  const c = ok === null ? 'bg-slate-100 text-slate-600' : ok ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${c}`}>{children}</span>
}

export function Stat({ label, value, hint, tone = 'slate' }: { label: string; value: ReactNode; hint?: string; tone?: 'slate' | 'green' | 'red' | 'indigo' }) {
  const t = { slate: 'text-slate-900', green: 'text-emerald-700', red: 'text-red-700', indigo: 'text-indigo-700' }[tone]
  return (
    <div className="card px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${t}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </div>
  )
}

export function Legend({ roles }: { roles: Role[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {roles.map((r) => <RoleChip key={r} role={r} />)}
    </div>
  )
}

/** Shown on analysis pages until CAIF has been run. */
export function NeedsRun({ children }: { children: ReactNode }) {
  const { result, run, busy, source, stale } = useApp()
  if (!result) {
    return (
      <Card>
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <p className="text-slate-600">No analysis yet. Run CAIF on the current program to populate this page.</p>
          <div className="flex gap-2">
            <button className="btn-primary" disabled={busy || !source.trim()} onClick={() => run()}>Run CAIF optimization</button>
            <Link to="/input" className="btn-secondary">Go to Instruction Input</Link>
          </div>
        </div>
      </Card>
    )
  }
  return (
    <>
      {stale && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          The program or configuration changed since the last run, so the results below are out of date.
          <button className="btn-secondary !py-1" disabled={busy} onClick={() => run()}>Re-run</button>
        </div>
      )}
      {children}
    </>
  )
}

export function StatusBanner() {
  const { result } = useApp()
  if (!result) return null
  const s = result.status
  const tone = s === 'OPTIMIZED' ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
    : s === 'UNCHANGED' ? 'border-slate-300 bg-slate-50 text-slate-800' : 'border-red-300 bg-red-50 text-red-900'
  const text = s === 'OPTIMIZED'
    ? `Success: ${result.metrics.successful_rearrangements} safe rearrangement(s) applied; the result passed the static re-check and differential execution.`
    : s === 'UNCHANGED'
      ? (result.metrics.rejected_rearrangements
        ? `No change: ${result.metrics.rejected_rearrangements} candidate move(s) were rejected because they could not be proven safe.`
        : 'No change: there was no non-consecutive compatible pair to rearrange.')
      : 'The validator rejected the optimized sequence. The original program is kept.'
  return <div className={`mb-4 rounded-lg border px-4 py-3 text-sm font-medium ${tone}`}>{s.replace(/_/g, ' ')} | {text}</div>
}
