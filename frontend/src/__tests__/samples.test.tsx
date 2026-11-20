import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { AppStateProvider } from '../state/AppState'
import backend from './fixtures/backend.json'

describe('sample programs on the Input page', () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

  it('lists every sample and loads one on click', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
      ok: true, status: 200,
      json: async () => (url.endsWith('/api/examples') ? backend.examples : url.endsWith('/api/configs') ? [] : { status: 'ok' }),
    })))
    render(<MemoryRouter initialEntries={['/input']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppStateProvider><App /></AppStateProvider></MemoryRouter>)
    await waitFor(() => expect(screen.getByText(`Sample programs (${backend.examples.length})`)).toBeInTheDocument())
    const target = backend.examples[8]
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: target.title })) })
    expect(screen.getByLabelText('Program source')).toHaveValue(target.source)
  })

  it('retries when the backend is not reachable at first', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let up = false
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (!up) throw new TypeError('connection refused')
      return { ok: true, status: 200, json: async () => (url.endsWith('/api/examples') ? backend.examples : []) }
    }))
    render(<MemoryRouter initialEntries={['/input']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppStateProvider><App /></AppStateProvider></MemoryRouter>)
    await waitFor(() => expect(screen.getByText(/retrying every 3 s/)).toBeInTheDocument())
    up = true
    await act(async () => { vi.advanceTimersByTime(3100) })
    await waitFor(() => expect(screen.getByText(`Sample programs (${backend.examples.length})`)).toBeInTheDocument())
    expect(screen.queryByText(/Cannot reach the backend/)).not.toBeInTheDocument()
  })
})
