import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { AppStateProvider } from '../state/AppState'
import fixture from './fixtures/backend.json'

// React Flow needs these browser APIs, which jsdom lacks
class RO { observe() {} unobserve() {} disconnect() {} }
;(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO
;(globalThis as unknown as { DOMMatrixReadOnly: unknown }).DOMMatrixReadOnly = class { m22 = 1; constructor() {} }

function mockFetch() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const body =
      url.endsWith('/api/health') ? { status: 'ok' }
        : url.endsWith('/api/examples') ? fixture.examples
          : url.endsWith('/api/optimize') ? fixture.optimize
            : url.endsWith('/api/experiments/results') ? []
              : url.endsWith('/api/configs') ? [] : {}
    return { ok: true, status: 200, json: async () => body }
  }))
}

async function renderAt(path: string) {
  mockFetch()
  render(<MemoryRouter initialEntries={['/input']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppStateProvider><App /></AppStateProvider></MemoryRouter>)
  await waitFor(() => expect(screen.getByLabelText('Program source')).not.toHaveValue(''))
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Run CAIF optimization' })) })
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('CAIF finished'))
  const link = screen.getAllByRole('link').find((a) => a.getAttribute('href') === path)!
  await act(async () => { fireEvent.click(link) })
}

describe('every page renders with real backend output', () => {
  afterEach(() => vi.restoreAllMocks())
  it('Overview', async () => { await renderAt('/'); expect(screen.getByText(/nine separate, testable stages/)).toBeInTheDocument() })
  it('Fusion Analysis', async () => {
    await renderAt('/analysis')
    expect(screen.getByText('Candidate memory instruction pairs')).toBeInTheDocument()
    expect(screen.getAllByText('rejected').length).toBeGreaterThan(0)
  })
  it('Dependency graph', async () => { await renderAt('/dependencies'); expect(screen.getByTestId('dep-graph')).toBeInTheDocument() })
  it('Optimization', async () => {
    await renderAt('/optimization')
    expect(screen.getByText(/Step-by-step explanation/)).toBeInTheDocument()
    expect(screen.getByText('differential_execution')).toBeInTheDocument()
  })
  it('Results', async () => { await renderAt('/results'); expect(screen.getByText(/Results reported in the paper/)).toBeInTheDocument() })
  it('About', async () => { await renderAt('/about'); expect(screen.getByText('Use-def chains')).toBeInTheDocument() })
})
