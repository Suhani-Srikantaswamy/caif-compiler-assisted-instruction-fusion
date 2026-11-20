import type { Instruction } from '../types/caif'

export function InstructionTable({ instructions }: { instructions: Instruction[] }) {
  if (!instructions.length) return <p className="text-sm text-slate-500">No instructions.</p>
  return (
    <div className="overflow-x-auto">
      <table className="tbl">
        <thead>
          <tr>
            <th>#</th><th>ID</th><th>Block</th><th>Instruction</th><th>Category</th><th>Dest</th><th>Sources</th>
            <th>Memory (base / off / size)</th><th>Mem op</th><th>Depends on</th><th>Meaning</th>
          </tr>
        </thead>
        <tbody>
          {instructions.map((i) => (
            <tr key={i.id}>
              <td className="tabular-nums text-slate-400">{i.position}</td>
              <td className="mono font-semibold">{i.id}</td>
              <td className="mono text-slate-500">{i.block}</td>
              <td className="mono whitespace-nowrap">{i.text}</td>
              <td><span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{i.category}</span></td>
              <td className="mono">{i.dest ?? '-'}</td>
              <td className="mono">{i.sources.join(', ') || '-'}</td>
              <td className="mono whitespace-nowrap">
                {i.mem ? `${i.mem.base}${i.mem.base_is_register ? ' (reg)' : ' (sym)'} / ${i.mem.offset} / ${i.mem.size} B` : '-'}
              </td>
              <td className="text-xs">{i.mem_kind === 'NONE' ? '-' : i.mem_kind}</td>
              <td className="mono text-xs">{i.depends_on.join(', ') || '-'}</td>
              <td className="text-xs text-slate-500">{i.explanation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
