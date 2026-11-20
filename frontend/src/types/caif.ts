// Types mirroring the FastAPI response models (backend/api_schemas.py)

export type Target = 'ConsSBR' | 'ConsSBR64' | 'Cons'

export interface FusionConfig {
  target: Target
  window_bytes: number
  allow_load_pairs: boolean
  allow_store_pairs: boolean
  require_same_size: boolean
  max_instruction_distance: number | null
  default_size: 1 | 2 | 4 | 8
}

export const DEFAULT_CONFIG: FusionConfig = {
  target: 'ConsSBR64',
  window_bytes: 64,
  allow_load_pairs: true,
  allow_store_pairs: true,
  require_same_size: false,
  max_instruction_distance: null,
  default_size: 8,
}

export interface MemOperand {
  base: string
  base_is_register: boolean
  offset: number
  size: number
}

export interface Instruction {
  id: string
  index: number
  position: number
  original_position?: number
  line: number
  opcode: string
  category: string
  text: string
  dest: string | null
  sources: string[]
  immediates: number[]
  mem: MemOperand | null
  mem_kind: string
  symbol: string | null
  block: string
  explanation: string
  depends_on: string[]
}

export interface ParseError { line: number; message: string; text: string }

export interface ParseResponse {
  ok: boolean
  instructions: Instruction[]
  errors: ParseError[]
  blocks: string[]
}

export interface Edge { src: string; dst: string; type: string; subtype: string; reason: string }
export interface Graph { nodes: string[]; edges: Edge[]; counts: Record<string, number> }

export interface Condition { name: string; passed: boolean; detail: string }

export interface MemInfo {
  ins_id: string; kind: string; base: string; offset: number; size: number
  address: string; range: string; base_key: string
}

export interface Candidate {
  head: string; tail: string; head_pos: number; tail_pos: number
  kind: string; compatible: boolean; consecutive: boolean
  fusion_class: string | null; byte_distance: number | null; span_bytes: number | null
  instruction_distance: number; catalyst_size: number; rearrangement_useful: boolean
  conditions: Condition[]
  head_text?: string; tail_text?: string
  head_mem?: MemInfo; tail_mem?: MemInfo
}

export interface CatalystEntry {
  id: string; text: string; position: number
  depends_on_head: boolean; head_edges: string[]
  in_tail_chain: boolean; provides: string | null
  memory_effect: string; action: 'MOVES_WITH_TAIL' | 'STAYS'
  can_remain: boolean; blocking: string[]
}

export interface CatalystReport {
  head: string; tail: string; catalyst: string[]; chain: string[]
  head_in_chain: boolean; safe: boolean; reasons: string[]
  violations: Edge[]; entries: CatalystEntry[]; proposed_order: string[]
}

export interface Step {
  number: number
  action: 'CONSECUTIVE' | 'REARRANGED' | 'REJECTED'
  head: string; tail: string
  pair: Candidate
  catalyst: CatalystReport | null
  before: string[]; after: string[]; moved: string[]
  explanation: string[]
}

export interface Check { name: string; passed: boolean; details: string }
export interface Validation { valid: boolean; checks: Check[]; errors: string[] }

export interface Metrics {
  total_instructions: number
  memory_instructions: number
  load_instructions: number
  store_instructions: number
  dependencies: number
  dependency_counts: Record<string, number>
  compatible_candidate_pairs: number
  non_consecutive_candidate_pairs: number
  consecutive_before: number
  consecutive_after: number
  additional_opportunities: number
  percent_increase: number | null
  rearrangements_attempted: number
  successful_rearrangements: number
  rejected_rearrangements: number
  blocked_heads: string[]
  instructions_moved: string[]
  fused_memory_ops_before_pct: number
  fused_memory_ops_after_pct: number
  fusion_class_before: Record<string, number>
  fusion_class_after: Record<string, number>
  optimizer_time_ms: number
  analysis_time_ms: number
  validation_time_ms: number
  total_time_ms: number
  note: string
}

export interface OptimizeResponse {
  instructions: Instruction[]
  blocks: string[]
  memory: Record<string, MemInfo>
  graph: Graph
  candidates: Candidate[]
  catalyst_reports: Record<string, CatalystReport>
  config: FusionConfig
  status: 'OPTIMIZED' | 'UNCHANGED' | 'REJECTED_BY_VALIDATOR'
  optimized: Instruction[]
  optimized_graph: Graph
  steps: Step[]
  pairs: [string, string][]
  proposed_order: string[]
  validation: Validation
  opportunities_before: Candidate[]
  opportunities_after: Candidate[]
  metrics: Metrics
}

export interface Sample {
  id: string; title: string; kind: 'success' | 'rejected' | 'mixed'
  description: string; expected: string; dependencies: string
  should_rearrange: boolean; config: Partial<FusionConfig>; source: string
}

export interface ExperimentRow {
  sample_id: string; title: string; kind: string; target: string
  instructions: number; memory_instructions: number; candidate_pairs: number; dependencies: number
  rearrangements_attempted: number; successful_rearrangements: number; rejected_rearrangements: number
  consecutive_before: number; consecutive_after: number; additional_opportunities: number
  percent_increase: number | null
  fused_memory_ops_before_pct: number; fused_memory_ops_after_pct: number
  optimizer_time_ms: number; validation_passed: boolean; status: string
  expected_rearrange: boolean; matches_specification: boolean; rejection_reasons: string[]
}

export interface SweepRow {
  target: string; window_bytes: number; consecutive_before: number; consecutive_after: number
  successful_rearrangements: number; rejected_rearrangements: number
}

export interface ExperimentRun {
  id: string; created: string; label: string; note: string
  overrides: Record<string, unknown>
  rows: ExperimentRow[]
  totals: Record<string, number | boolean>
  sweep: SweepRow[]
  files?: { json: string; csv: string }
}

export interface ExperimentSummary {
  id: string; created: string; label: string; samples: number; totals: Record<string, number | boolean>
}
