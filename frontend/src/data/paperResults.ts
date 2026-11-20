// Values REPORTED BY THE PAPER (Reddy et al., CGO 2026). They were produced by the
// authors' LLVM implementation and cycle-level RISC-V simulation. They are NOT
// produced by this project and must never be mixed with local results.

export const PAPER = {
  title: 'Compiler-Assisted Instruction Fusion',
  authors: ['Ravikiran Ravindranath Reddy', 'Sawan Singh', 'Arthur Perais', 'Alberto Ros', 'Alexandra Jimborean'],
  venue: 'IEEE/ACM International Symposium on Code Generation and Optimization (CGO 2026)',
  pdf: 'https://webs.um.es/aros/papers/pdfs/rrreddy-cgo26.pdf',
  page: 'https://2026.cgo.org/details/cgo-2026-papers/34/Compiler-Assisted-Instruction-Fusion',
}

/** Average execution-time reduction vs. NoFusion-Base, neural-network kernels, Gracemont-like core (Sec. VI-D, Fig. 9). */
export const PAPER_NN_EXEC = [
  { config: 'ConsSBR', base: 1.1, caif: 19.1 },
  { config: 'ConsSBR64', base: 1.2, caif: 19.6 },
  { config: 'Helios', base: 6.6, caif: 20.3 },
]

export const PAPER_FACTS: { metric: string; value: string; source: string }[] = [
  { metric: 'NN: memory ops fused as Consecutive-SBR-contiguous', value: '1.94% -> 61.67%', source: 'Sec. VI-A' },
  { metric: 'NN: non-consecutive fusion needed by Helios', value: '27.12% -> 8.96%', source: 'Sec. VI-A' },
  { metric: 'NN: fused instructions, ConsSBR64-CAIF vs Helios-Base', value: '70.61% vs 29.93%', source: 'Sec. VI-A' },
  { metric: 'SPEC: fused instructions, ConsSBR64 Base -> CAIF (Helios-Base)', value: '23.51% -> 39.8% (40.69%)', source: 'Sec. VI-A' },
  { metric: 'NN: exec. time, NoFusion-CAIF vs NoFusion-Base', value: '~5% reduction', source: 'Sec. VI-D' },
  { metric: 'SPEC: exec. time reduction, ConsSBR64 Base -> CAIF', value: '2.6% -> 6.6% (abstract: 2.4% -> 6.4%)', source: 'Sec. VI-D / Abstract' },
  { metric: 'SPEC: exec. time reduction, Helios Base -> CAIF', value: '14.4% -> 17.7%', source: 'Abstract' },
  { metric: 'Average catalyst depth (Helios), NN / SPEC', value: '4.16 -> 1.68 / 3.60 -> 2.88', source: 'Sec. VI-D, Fig. 10' },
  { metric: 'Fusion mispredictions (MPKI), Helios Base -> CAIF', value: '0.31 -> 0.29', source: 'Sec. VI-B' },
  { metric: 'L1D access reduction vs NoFusion-Base', value: 'ConsSBR64-CAIF 31.28%, Helios-CAIF 38.17%', source: 'Sec. VI-E' },
  { metric: 'Max. binary size increase', value: '+0.31% (xalancbmk)', source: 'Sec. VI-D' },
]
