import { computeRoles } from '../lib/roles'
import { layoutGraph } from '../graphs/layout'
import type { CatalystReport } from '../types/caif'

const rep: CatalystReport = {
  head: 'H', tail: 'T', catalyst: ['C1', 'C2', 'C3'], chain: ['C2'], head_in_chain: false, safe: false,
  reasons: [], violations: [{ src: 'C3', dst: 'T', type: 'MEMORY', subtype: 'MEM-RAW', reason: '' }],
  entries: [], proposed_order: [],
}

describe('computeRoles', () => {
  it('assigns HEAD/TAIL/CATALYST/REQUIRED/BLOCKED', () => {
    const r = computeRoles(rep)
    expect(r).toMatchObject({ H: 'HEAD', T: 'TAIL', C1: 'CATALYST', C2: 'REQUIRED', C3: 'BLOCKED' })
  })
  it('marks fused instructions when no pair is selected', () => {
    expect(computeRoles(null, ['A', 'B'])).toEqual({ A: 'FUSION', B: 'FUSION' })
  })
})

describe('layoutGraph', () => {
  it('places rows by program order and columns by dependence depth', () => {
    const p = layoutGraph(['a', 'b', 'c'], [
      { src: 'a', dst: 'b', type: 'RAW', subtype: 'R1', reason: '' },
      { src: 'b', dst: 'c', type: 'RAW', subtype: 'R2', reason: '' },
    ], 100, 10)
    expect(p.a).toEqual({ x: 0, y: 0, depth: 0 })
    expect(p.c).toEqual({ x: 200, y: 20, depth: 2 })
  })
  it('keeps independent instructions in the first column', () => {
    const p = layoutGraph(['a', 'b'], [])
    expect(p.b.depth).toBe(0)
  })
})
