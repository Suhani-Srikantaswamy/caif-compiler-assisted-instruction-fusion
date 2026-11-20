import { Link } from 'react-router-dom'
import { Card, PageHeader } from '../components/ui'
import { PAPER } from '../data/paperResults'

const PAPER_PIPELINE = [
  { t: 'Front end', d: 'C/C++ (clang) or PyTorch -> ONNX -> MLIR' },
  { t: 'LLVM IR (middle end)', d: 'opt -O3, then CAIF: alias analysis, use-def chains, loop unrolling, reordering', caif: true },
  { t: 'Back end', d: 'llc -O3 + CAIF pseudo-instructions and DAG mutations keep the pairs together', caif: true },
  { t: 'RISC-V binary', d: 'fusible memory ops are now adjacent' },
  { t: 'Hardware decoder', d: 'simple non-speculative consecutive fusion (ConsSBR / ConsSBR64)' },
]

const OUR_STAGES = [
  ['1', 'Input', 'educational assembly text'],
  ['2', 'Parse', 'structured Instruction objects'],
  ['3', 'Candidates', 'compatible LOAD/STORE pairs'],
  ['4', 'Dependences', 'RAW / WAR / WAW / MEMORY + alias analysis'],
  ['5', 'Catalyst', 'instructions between HEAD and TAIL'],
  ['6', 'Rearrange', 'hoist use-def chain + TAIL'],
  ['7', 'Validate', 'static re-check + interpreter-based differential test'],
  ['8', 'Detect', 'consecutive fusion opportunities'],
  ['9', 'Results', 'tables, graphs, experiments'],
]

export default function Overview() {
  return (
    <div className="space-y-6">
      <PageHeader title="CAIF: Compiler-Assisted Instruction Fusion"
        subtitle="An educational re-implementation of the central idea of a CGO 2026 paper: the compiler safely reorders instructions so that fusible memory operations end up next to each other, where simple hardware can fuse them." />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Research paper" className="lg:col-span-2">
          <div className="space-y-2 text-sm">
            <div className="text-base font-semibold text-slate-900">{PAPER.title}</div>
            <div className="text-slate-600">{PAPER.authors.join(', ')}</div>
            <div className="text-slate-500">{PAPER.venue}</div>
            <div className="flex flex-wrap gap-3 pt-1">
              <a className="text-indigo-600 hover:underline" href={PAPER.pdf} target="_blank" rel="noreferrer">Paper PDF</a>
              <a className="text-indigo-600 hover:underline" href={PAPER.page} target="_blank" rel="noreferrer">Conference page</a>
            </div>
          </div>
        </Card>
        <Card title="Get started">
          <p className="mb-3 text-sm text-slate-600">Pick a sample program, run CAIF, then walk through the analysis pages in order.</p>
          <Link to="/input" className="btn-primary">Open Instruction Input</Link>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card title="What is instruction fusion?">
          <p className="text-sm leading-relaxed text-slate-600">
            The processor's decoder merges two adjacent instructions into one internal micro-operation. A fused pair takes a single
            entry in the reorder buffer and the load/store queues, and needs one cache access instead of two. This frees resources
            and saves energy. Memory pairs that touch the same 64-byte region benefit most.
          </p>
        </Card>
        <Card title="The problem">
          <p className="text-sm leading-relaxed text-slate-600">
            Cheap fusion hardware only sees <b>consecutive</b> instructions. Compilers often place fusible loads far apart, for example
            in interleaved, unrolled loops. Hardware that fuses non-consecutive pairs (e.g. Helios) needs predictors, validation and
            recovery logic. In the paper's neural-network kernels only 1.94% of memory operations formed consecutive, same-base, contiguous pairs, the only kind the simplest hardware fuses (Sec. III-A).
          </p>
        </Card>
        <Card title="The CAIF idea">
          <p className="text-sm leading-relaxed text-slate-600">
            Move the complexity into the compiler. It finds fusible pairs (HEAD and TAIL), analyses the instructions between them (the
            <i> catalyst</i>), proves with dependence and alias analysis (under its memory model) that the TAIL and its use-def chain can move up, and makes the
            pair consecutive. No prediction and no misspeculation recovery are needed.
          </p>
        </Card>
      </div>

      <Card title="Where CAIF sits in the paper's compiler pipeline">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-stretch">
          {PAPER_PIPELINE.map((s, i) => (
            <div key={s.t} className="flex flex-1 items-center gap-2 lg:flex-col lg:items-stretch">
              <div className={`flex-1 rounded-lg border p-3 ${s.caif ? 'border-emerald-400 bg-emerald-50' : 'border-slate-200 bg-slate-50'}`}>
                <div className="text-sm font-semibold">{s.t}{s.caif && <span className="ml-1 rounded bg-emerald-500 px-1 text-[10px] font-semibold text-emerald-50">CAIF</span>}</div>
                <div className="mt-1 text-xs text-slate-600">{s.d}</div>
              </div>
              {i < PAPER_PIPELINE.length - 1 && <div className="text-center text-slate-400 lg:hidden">↓</div>}
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">Based on Fig. 3 of the paper. The green stages are the authors' LLVM passes; this project re-creates the middle-end reordering logic in Python.</p>
      </Card>

      <Card title="This prototype: nine separate, testable stages">
        <ol className="grid gap-2 sm:grid-cols-3 lg:grid-cols-9">
          {OUR_STAGES.map(([n, t, d]) => (
            <li key={n} className="rounded-lg border border-slate-200 bg-slate-100 p-3">
              <div className="text-xs font-semibold text-indigo-600">Stage {n}</div>
              <div className="text-sm font-semibold">{t}</div>
              <div className="mt-1 text-xs text-slate-500">{d}</div>
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Technology stack">
          <ul className="space-y-1 text-sm text-slate-600">
            <li><b>Backend:</b> Python 3, FastAPI, Pydantic. Compiler logic in <code className="mono">backend/core/</code></li>
            <li><b>Frontend:</b> React, TypeScript, Vite, Tailwind CSS</li>
            <li><b>Visualisation:</b> React Flow (dependency graphs), Recharts (results)</li>
            <li><b>Testing:</b> Pytest (backend), Vitest + Testing Library (frontend)</li>
            <li><b>Storage:</b> local JSON/CSV in <code className="mono">data/</code></li>
          </ul>
        </Card>
        <Card title="Honesty notes">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
            <li>The instruction set is a simulated teaching ISA, not RISC-V machine code.</li>
            <li>This project counts <b>potential</b> consecutive fusion opportunities. It never measures hardware fusion or speedup.</li>
            <li>Numbers reported in the paper are shown separately and clearly labelled on the Results page.</li>
          </ul>
        </Card>
      </div>
    </div>
  )
}
