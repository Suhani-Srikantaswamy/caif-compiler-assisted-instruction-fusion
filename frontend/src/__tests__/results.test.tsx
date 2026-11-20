import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { AppStateProvider } from '../state/AppState'
import backend from './fixtures/backend.json'
import run from './fixtures/experiment.json'
import list from './fixtures/experiments_list.json'

class RO { observe() {} unobserve() {} disconnect() {} }
;(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO

describe('Results page with saved experiments', () => {
  afterEach(() => vi.restoreAllMocks())
  it('renders the latest saved run', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const body = url.endsWith('/api/health') ? { status: 'ok' }
        : url.endsWith('/api/examples') ? backend.examples
          : url.endsWith('/api/experiments/results') ? list
            : url.includes('/api/experiments/') ? run
              : url.endsWith('/api/configs') ? [] : {}
      return { ok: true, status: 200, json: async () => body }
    }))
    render(<MemoryRouter initialEntries={['/results']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppStateProvider><App /></AppStateProvider></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Per-sample table')).toBeInTheDocument())
    expect(screen.getByText(/Results reported in the paper/)).toBeInTheDocument()
  })
})
