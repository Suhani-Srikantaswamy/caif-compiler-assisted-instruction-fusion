import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useApp } from '../state/AppState'
import type { FusionConfig, Target } from '../types/caif'

const TARGET_HELP: Record<Target, string> = {
  ConsSBR: 'Same base register, contiguous accesses only',
  ConsSBR64: 'Same base register, both accesses inside the window (default)',
  Cons: 'Also different base registers, if the distance is provable',
}

export function ConfigPanel() {
  const { config, setConfig } = useApp()
  const [saved, setSaved] = useState<{ name: string; config: FusionConfig }[]>([])
  const [name, setName] = useState('')
  const set = <K extends keyof FusionConfig>(k: K, v: FusionConfig[K]) => setConfig({ ...config, [k]: v })

  useEffect(() => { api.configs().then(setSaved).catch(() => undefined) }, [])

  return (
    <div className="space-y-4 text-sm">
      <label className="block">
        <span className="font-medium text-slate-700">Target fusion model</span>
        <select className="mt-1 w-full rounded-md border-slate-300 border px-2 py-1.5" value={config.target}
          onChange={(e) => set('target', e.target.value as Target)}>
          {(Object.keys(TARGET_HELP) as Target[]).map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <span className="mt-1 block text-xs text-slate-500">{TARGET_HELP[config.target]}</span>
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="font-medium text-slate-700">Window (bytes)</span>
          <input type="number" min={1} max={4096} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5"
            value={config.window_bytes} onChange={(e) => set('window_bytes', Math.max(1, Number(e.target.value) || 1))} />
        </label>
        <label className="block">
          <span className="font-medium text-slate-700">Default size</span>
          <select className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5" value={config.default_size}
            onChange={(e) => set('default_size', Number(e.target.value) as FusionConfig['default_size'])}>
            {[1, 2, 4, 8].map((s) => <option key={s} value={s}>{s} B</option>)}
          </select>
        </label>
        <label className="col-span-2 block">
          <span className="font-medium text-slate-700">Max instruction distance</span>
          <input type="number" min={1} placeholder="whole basic block" className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5"
            value={config.max_instruction_distance ?? ''}
            onChange={(e) => set('max_instruction_distance', e.target.value ? Math.max(1, Number(e.target.value)) : null)} />
        </label>
      </div>
      <div className="space-y-1.5">
        {([['allow_load_pairs', 'Fuse LOAD + LOAD'], ['allow_store_pairs', 'Fuse STORE + STORE'], ['require_same_size', 'Require equal access sizes']] as const).map(([k, label]) => (
          <label key={k} className="flex items-center gap-2">
            <input type="checkbox" checked={config[k]} onChange={(e) => set(k, e.target.checked)} />
            {label}
          </label>
        ))}
      </div>
      <div className="border-t border-slate-100 pt-3">
        <div className="mb-1 font-medium text-slate-700">Saved configurations</div>
        <div className="flex gap-2">
          <input className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1" placeholder="name" value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn-secondary !py-1" disabled={!name.trim()}
            onClick={() => api.saveConfig(name.trim(), config).then((c) => { setSaved(c); setName('') })}>Save</button>
        </div>
        {saved.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {saved.map((s) => (
              <button key={s.name} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs hover:bg-indigo-100" onClick={() => setConfig(s.config)}>{s.name}</button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
