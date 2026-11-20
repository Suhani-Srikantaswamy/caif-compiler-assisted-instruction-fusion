import type {
  ExperimentRun, ExperimentSummary, FusionConfig, OptimizeResponse, ParseError, ParseResponse, Sample, Validation,
} from '../types/caif'

export class ApiError extends Error {
  errors: ParseError[]
  constructor(message: string, errors: ParseError[] = []) {
    super(message)
    this.errors = errors
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError('Cannot reach the backend at /api. Is uvicorn running on port 8000?')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const d = body?.detail
    if (d && typeof d === 'object' && 'message' in d) throw new ApiError(d.message, d.errors ?? [])
    if (Array.isArray(d)) throw new ApiError(d.map((x: { msg: string; loc: unknown[] }) => `${x.loc.join('.')}: ${x.msg}`).join('; '))
    throw new ApiError(`Request failed (${res.status})`)
  }
  return body as T
}

const post = <T>(path: string, data: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(data) })

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  examples: () => request<Sample[]>('/api/examples'),
  parse: (source: string, config: FusionConfig) => post<ParseResponse>('/api/parse', { source, config }),
  optimize: (source: string, config: FusionConfig) => post<OptimizeResponse>('/api/optimize', { source, config }),
  validate: (source: string, order: string[], config: FusionConfig) =>
    post<Validation>('/api/validate', { source, order, config }),
  runExperiments: (label: string, overrides: Record<string, unknown> = {}) =>
    post<ExperimentRun>('/api/experiments/run', { label, overrides, sweep: true }),
  experiments: () => request<ExperimentSummary[]>('/api/experiments/results'),
  experiment: (id: string) => request<ExperimentRun>(`/api/experiments/${encodeURIComponent(id)}`),
  report: (id: string) => request<{ id: string; markdown: string }>(`/api/report/${encodeURIComponent(id)}`),
  configs: () => request<{ name: string; config: FusionConfig }[]>('/api/configs'),
  saveConfig: (name: string, config: FusionConfig) =>
    post<{ name: string; config: FusionConfig }[]>('/api/configs', { name, config }),
}
