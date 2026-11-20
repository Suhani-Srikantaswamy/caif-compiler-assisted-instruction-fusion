import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { ConfigPanel } from '../components/ConfigPanel'
import { InstructionTable } from '../components/InstructionTable'
import { Card, PageHeader } from '../components/ui'
import { useApp } from '../state/AppState'

const SYNTAX = `LOAD R1, [A+0]        LOAD.4 R1, [R3+8]
STORE [B+8], R2       ADD/SUB/MUL Rd, Rs, Rt|imm
MOV Rd, Rs|imm        ADDR Rd, SYMBOL, offset
CMP Rs, Rt|imm        BR|BEQ|BNE label   CALL f   NOP
label:                ID: instruction    ; comment`

export default function InputPage() {
  const { source, setSource, samples, sampleId, loadSample, parse, run, clear, busy, errors, message, parsed, result, backendOk } = useApp()
  const taRef = useRef<HTMLTextAreaElement>(null)
  const gutterRef = useRef<HTMLDivElement>(null)
  const sample = samples.find((s) => s.id === sampleId)
  const lines = Math.max(source.split('\n').length, 12)
  const errLines = new Set(errors.map((e) => e.line))

  return (
    <div className="space-y-6">
      <PageHeader title="Instruction Input"
        subtitle="Write or paste a program in the educational assembly syntax, or load one of the predefined workloads. This is a simulated ISA for teaching, not real machine code." />

      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <Card title={`Sample programs (${samples.length})`} right={
            <span className="flex gap-3 text-xs font-normal text-slate-500">
              <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />rearranged</span>
              <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />rejected</span>
              <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-500" />mixed</span>
            </span>
          }>
            {samples.length === 0 ? (
              <p className="text-sm text-slate-500">
                {backendOk === false ? 'Waiting for the backend to load the sample programs (retrying every 3 s)...' : 'Loading sample programs...'}
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2 2xl:grid-cols-3">
                {samples.map((s) => (
                  <button key={s.id} onClick={() => loadSample(s.id)} aria-pressed={sampleId === s.id}
                    className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm transition
                      ${sampleId === s.id ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'}`}>
                    <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${s.kind === 'success' ? 'bg-emerald-500' : s.kind === 'rejected' ? 'bg-red-500' : 'bg-amber-500'}`} />
                    <span className="text-slate-700">{s.title}</span>
                  </button>
                ))}
              </div>
            )}
          </Card>

          <Card title={sample ? `Program editor: ${sample.title}` : 'Program editor: custom program'}>
            {sample && (
              <div className="mb-4 rounded-lg bg-slate-50 p-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${sample.kind === 'success' ? 'bg-emerald-100 text-emerald-800' : sample.kind === 'rejected' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'}`}>{sample.kind}</span>
                  <span className="text-slate-700">{sample.description}</span>
                </div>
                <div className="mt-2 text-xs text-slate-500"><b>Expected:</b> {sample.expected}</div>
                <div className="mt-1 text-xs text-slate-500"><b>Dependences:</b> {sample.dependencies}</div>
                {Object.keys(sample.config).length > 0 && <div className="mt-1 text-xs text-slate-500"><b>Config:</b> {JSON.stringify(sample.config)}</div>}
              </div>
            )}
            <div className="flex overflow-hidden rounded-lg border border-slate-300 bg-slate-50 focus-within:ring-2 focus-within:ring-indigo-400">
              <div ref={gutterRef} className="select-none overflow-hidden bg-slate-100 py-3 text-right font-mono text-[13px] leading-6 text-slate-500" aria-hidden>
                {Array.from({ length: lines }, (_, i) => (
                  <div key={i} className={`px-2 ${errLines.has(i + 1) ? 'bg-red-500/30 text-red-800' : ''}`}>{i + 1}</div>
                ))}
              </div>
              <textarea ref={taRef} aria-label="Program source" spellCheck={false}
                className="min-h-[300px] flex-1 resize-y bg-transparent p-3 font-mono text-[13px] leading-6 text-slate-800 outline-none placeholder:text-slate-400"
                rows={lines} value={source} onChange={(e) => setSource(e.target.value)}
                onScroll={(e) => { if (gutterRef.current) gutterRef.current.scrollTop = e.currentTarget.scrollTop }}
                placeholder={'L1: LOAD R1, [A+0]\nADD R2, R3, R4\nL2: LOAD R5, [A+8]'} />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button className="btn-secondary" disabled={busy || !source.trim()} onClick={() => parse()}>Parse</button>
              <button className="btn-primary" disabled={busy || !source.trim()} onClick={() => run()}>{busy ? 'Running...' : 'Run CAIF optimization'}</button>
              <button className="btn-secondary" disabled={busy} onClick={() => { clear(); taRef.current?.focus() }}>Clear</button>
              {result && <Link className="btn-secondary" to="/analysis">View Fusion Analysis →</Link>}
            </div>
            {message && <div className={`mt-3 text-sm ${errors.length ? 'text-red-700' : 'text-slate-600'}`} role="status">{message}</div>}
            {errors.length > 0 && (
              <ul className="mt-2 space-y-1 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" aria-label="Errors">
                {errors.map((e, i) => (
                  <li key={i}><span className="mono font-semibold">{e.line ? `line ${e.line}` : 'program'}:</span> {e.message}
                    {e.text && <span className="mono ml-2 text-red-500">{e.text}</span>}</li>
                ))}
              </ul>
            )}
          </Card>

          <Card title={`Parsed instructions${parsed ? ` (${parsed.instructions.length}, blocks: ${parsed.blocks.join(', ')})` : ''}`}>
            {parsed ? <InstructionTable instructions={parsed.instructions} />
              : <p className="text-sm text-slate-500">Press <b>Parse</b> to see the structured representation.</p>}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Fusion configuration"><ConfigPanel /></Card>
          <Card title="Syntax">
            <pre className="whitespace-pre-wrap font-mono text-[11px] leading-5 text-slate-600">{SYNTAX}</pre>
            <p className="mt-2 text-xs text-slate-500">Symbols (A, B, buf) are distinct memory objects. Register bases (R3) are pointers. A line with only <code>name:</code> starts a new basic block.</p>
          </Card>
        </div>
      </div>
    </div>
  )
}
