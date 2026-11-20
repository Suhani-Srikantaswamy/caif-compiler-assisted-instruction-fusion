import { render, screen } from '@testing-library/react'
import { InstructionTable } from '../components/InstructionTable'
import type { Instruction } from '../types/caif'

const ins: Instruction = {
  id: 'L1', index: 0, position: 0, line: 1, opcode: 'LOAD', category: 'LOAD', text: 'LOAD.8 R1, [A+8]',
  dest: 'R1', sources: [], immediates: [], mem: { base: 'A', base_is_register: false, offset: 8, size: 8 },
  mem_kind: 'READ', symbol: null, block: 'B0', explanation: 'R1 <- memory[A+8]', depends_on: [],
}

describe('InstructionTable', () => {
  it('renders the parsed representation', () => {
    render(<InstructionTable instructions={[ins]} />)
    expect(screen.getByText('LOAD.8 R1, [A+8]')).toBeInTheDocument()
    expect(screen.getByText('A (sym) / 8 / 8 B')).toBeInTheDocument()
  })
  it('shows an empty state', () => {
    render(<InstructionTable instructions={[]} />)
    expect(screen.getByText('No instructions.')).toBeInTheDocument()
  })
})
