/**
 * A2.3 / TD-519 — recording an upload, then asking for its read.
 *
 * The upload answers at once with `reading: true`; `recordDocument` then asks for the read
 * (`documents/<id>/read/`) so the student still sees the verdict. If that second call fails, the
 * upload stands and the caller gets the recorded document ("still checking").
 */
import { recordDocument } from './documents'
import { apiRequest } from './client'

jest.mock('./client', () => ({ apiRequest: jest.fn() }))

const api = apiRequest as jest.MockedFunction<typeof apiRequest>
const PAYLOAD = { doc_type: 'ic', storage_path: 'b40/1/ic/abc' }

beforeEach(() => api.mockReset())

it('asks for the read straight after an upload that is still reading', async () => {
  api.mockResolvedValueOnce({ id: 7, reading: true, match_verdict: 'pending' })
  api.mockResolvedValueOnce({ id: 7, reading: false, match_verdict: 'match' })
  const doc = await recordDocument(PAYLOAD)
  expect(api).toHaveBeenNthCalledWith(2, '/api/v1/scholarship/documents/7/read/',
    expect.objectContaining({ method: 'POST' }))
  expect(doc.match_verdict).toBe('match')
})

it('keeps the recorded upload when the read call fails', async () => {
  api.mockResolvedValueOnce({ id: 8, reading: true, match_verdict: 'pending' })
  api.mockRejectedValueOnce(new Error('network'))
  const doc = await recordDocument(PAYLOAD)
  expect(doc).toEqual({ id: 8, reading: true, match_verdict: 'pending' })
})

it('makes no second call when the upload needs no read', async () => {
  api.mockResolvedValueOnce({ id: 9, match_verdict: 'match' })
  await recordDocument(PAYLOAD)
  expect(api).toHaveBeenCalledTimes(1)
})
