/**
 * AUDIT A1.7 (TD-467 / SEC-18): THE BROWSER NEVER ASKS STORAGE TO OVERWRITE.
 *
 * The two older upload clients PUT the file to a signed Supabase URL with `x-upsert: true`, which
 * asks Storage to write over whatever is already at that key. The server now signs these URLs with
 * `upsert=False`, and the browser stops asking — the same as the bursary-growth and development
 * uploads (`bursaryGrowth.ts`, `development.ts`), which never sent it.
 */
import { uploadFileToSignedUrl } from '@/lib/api'
import { uploadOrgRequestAttachment } from '@/lib/admin-api'

const realFetch = global.fetch

type Call = { url: string; init: RequestInit }
let calls: Call[] = []

beforeEach(() => {
  calls = []
  global.fetch = jest.fn(async (url: string, init: RequestInit = {}) => {
    calls.push({ url: String(url), init })
    const body = String(url).endsWith('/sign-upload/')
      ? { upload_url: 'https://storage.test/put?token=t', storage_path: 'requests/1/2/abc' }
      : { id: 2, attachments: [] }
    return { ok: true, status: 200, json: async () => body }
  }) as unknown as typeof global.fetch
})

afterEach(() => {
  global.fetch = realFetch
  jest.restoreAllMocks()
})

const putHeaders = () => {
  const put = calls.filter((c) => c.init.method === 'PUT')
  expect(put).toHaveLength(1)
  return put[0].init.headers as Record<string, string>
}

it('the document upload PUT does not send x-upsert', async () => {
  const file = new File(['%PDF-1.4'], 'ic.pdf', { type: 'application/pdf' })
  await uploadFileToSignedUrl('https://storage.test/put?token=t', file)
  const headers = putHeaders()
  expect(Object.keys(headers).map((k) => k.toLowerCase())).not.toContain('x-upsert')
  expect(headers['Content-Type']).toBe('application/pdf')
})

it('the request-attachment upload PUT does not send x-upsert', async () => {
  const file = new File(['png'], 'shot.png', { type: 'image/png' })
  await uploadOrgRequestAttachment(2, file, { token: 'tok' })
  const headers = putHeaders()
  expect(Object.keys(headers).map((k) => k.toLowerCase())).not.toContain('x-upsert')
  expect(headers['Content-Type']).toBe('image/png')
})

it('a file with no type still goes up as octet-stream, without x-upsert', async () => {
  const file = new File(['heic'], 'IMG_0001.HEIC', { type: '' })
  await uploadFileToSignedUrl('https://storage.test/put?token=t', file)
  expect(putHeaders()).toEqual({ 'Content-Type': 'application/octet-stream' })
})
