import { api, ApiError } from '../services/api'
import { DEFAULT_CONFIG } from '../types/caif'

describe('api client', () => {
  afterEach(() => vi.restoreAllMocks())
  it('turns structured backend errors into ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 422,
      json: async () => ({ detail: { message: 'The program has errors', errors: [{ line: 1, message: 'Invalid opcode', text: 'X' }] } }),
    }))
    await expect(api.optimize('X', DEFAULT_CONFIG)).rejects.toMatchObject({ message: 'The program has errors' })
    try { await api.optimize('X', DEFAULT_CONFIG) } catch (e) { expect((e as ApiError).errors[0].line).toBe(1) }
  })
  it('reports an unreachable backend clearly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
    await expect(api.health()).rejects.toThrow(/Cannot reach the backend/)
  })
})
