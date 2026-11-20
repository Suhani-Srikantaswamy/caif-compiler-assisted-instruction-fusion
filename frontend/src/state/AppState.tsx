import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, ApiError } from '../services/api'
import { DEFAULT_CONFIG, type FusionConfig, type OptimizeResponse, type ParseError, type ParseResponse, type Sample } from '../types/caif'

interface AppState {
  source: string
  setSource: (s: string) => void
  config: FusionConfig
  setConfig: (c: FusionConfig) => void
  samples: Sample[]
  sampleId: string | null
  loadSample: (id: string) => void
  parsed: ParseResponse | null
  result: OptimizeResponse | null
  /** true when the editor/config changed after the last successful run */
  stale: boolean
  errors: ParseError[]
  message: string | null
  busy: boolean
  backendOk: boolean | null
  parse: () => Promise<void>
  run: () => Promise<boolean>
  clear: () => void
  selectedPair: string | null
  setSelectedPair: (k: string | null) => void
}

const Ctx = createContext<AppState | null>(null)

export function pairKey(h: string, t: string) {
  return `${h}-${t}`
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [source, setSourceRaw] = useState('')
  const [config, setConfigRaw] = useState<FusionConfig>(DEFAULT_CONFIG)
  const [samples, setSamples] = useState<Sample[]>([])
  const [sampleId, setSampleId] = useState<string | null>(null)
  const [parsed, setParsed] = useState<ParseResponse | null>(null)
  const [result, setResult] = useState<OptimizeResponse | null>(null)
  const [stale, setStale] = useState(false)
  const [errors, setErrors] = useState<ParseError[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [backendOk, setBackendOk] = useState<boolean | null>(null)
  const [selectedPair, setSelectedPair] = useState<string | null>(null)
  const sourceRef = useRef(source)
  sourceRef.current = source

  // Load the sample programs, retrying every 3 s while the backend is unreachable
  // (e.g. the frontend was opened before uvicorn started, or the backend restarted).
  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = async () => {
      try {
        const s = await api.examples()
        if (cancelled) return
        setBackendOk(true)
        setSamples(s)
        // Only pre-fill the editor if the user has not typed anything yet.
        if (s.length && !sourceRef.current.trim()) {
          setSourceRaw(s[0].source)
          setSampleId(s[0].id)
          setConfigRaw({ ...DEFAULT_CONFIG, ...s[0].config })
        }
      } catch {
        if (cancelled) return
        setBackendOk(false)
        timer = setTimeout(load, 3000)
      }
    }
    load()
    return () => { cancelled = true; if (timer) clearTimeout(timer) }
  }, [])

  const setSource = useCallback((s: string) => { setSourceRaw(s); setStale(true); setSampleId(null) }, [])
  const setConfig = useCallback((c: FusionConfig) => { setConfigRaw(c); setStale(true) }, [])

  const loadSample = useCallback((id: string) => {
    const s = samples.find((x) => x.id === id)
    if (!s) return
    setSourceRaw(s.source)
    setConfigRaw({ ...DEFAULT_CONFIG, ...s.config })
    setSampleId(id)
    setParsed(null); setResult(null); setErrors([]); setMessage(null); setStale(false); setSelectedPair(null)
  }, [samples])

  const handle = (e: unknown) => {
    if (e instanceof ApiError) { setErrors(e.errors); setMessage(e.message) }
    else setMessage(String(e))
  }

  const parse = useCallback(async () => {
    setBusy(true); setMessage(null)
    try {
      const p = await api.parse(source, config)
      setParsed(p); setErrors(p.errors)
      setMessage(p.ok ? `Parsed ${p.instructions.length} instructions in ${p.blocks.length} basic block(s).` : `${p.errors.length} error(s) found.`)
    } catch (e) { handle(e) } finally { setBusy(false) }
  }, [source, config])

  const run = useCallback(async () => {
    setBusy(true); setMessage(null)
    try {
      const r = await api.optimize(source, config)
      setResult(r); setErrors([]); setStale(false)
      setParsed({ ok: true, instructions: r.instructions, errors: [], blocks: r.blocks })
      const first = r.candidates.find((c) => c.compatible && !c.consecutive) ?? r.candidates.find((c) => c.compatible)
      setSelectedPair(first ? pairKey(first.head, first.tail) : null)
      setMessage(`CAIF finished: ${r.status.replace(/_/g, ' ').toLowerCase()}.`)
      return true
    } catch (e) { handle(e); return false } finally { setBusy(false) }
  }, [source, config])

  const clear = useCallback(() => {
    setSourceRaw(''); setParsed(null); setResult(null); setErrors([]); setMessage(null); setSampleId(null); setSelectedPair(null)
  }, [])

  const value = useMemo<AppState>(() => ({
    source, setSource, config, setConfig, samples, sampleId, loadSample, parsed, result, stale, errors, message,
    busy, backendOk, parse, run, clear, selectedPair, setSelectedPair,
  }), [source, setSource, config, setConfig, samples, sampleId, loadSample, parsed, result, stale, errors, message,
    busy, backendOk, parse, run, clear, selectedPair])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useApp outside provider')
  return c
}
