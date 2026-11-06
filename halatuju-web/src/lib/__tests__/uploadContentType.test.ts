import { uploadContentType } from '../uploadContentType'
import { uploadFileToSignedUrl } from '@/lib/api/documents'
import { uploadOrgRequestAttachment } from '@/lib/admin-api/requests'
import { uploadLessonFile } from '@/lib/admin-api/development'
import { sendTaskFile } from '@/lib/api/bursaryGrowth'

describe('uploadContentType', () => {
  const cases: Array<[string, string]> = [
    ['a.pdf', 'application/pdf'], ['a.jpg', 'image/jpeg'], ['a.jpeg', 'image/jpeg'],
    ['a.png', 'image/png'], ['a.webp', 'image/webp'], ['a.heic', 'image/heic'],
    ['a.heif', 'image/heif'], ['a.gif', 'image/gif'], ['a.bmp', 'image/bmp'],
    ['a.tif', 'image/tiff'], ['a.tiff', 'image/tiff'],
  ]
  it.each(cases)('empty type, %s -> %s', (name, mime) => {
    expect(uploadContentType(new File(['x'], name, { type: '' }))).toBe(mime)
  })
  it('keeps a type the browser set', () => {
    expect(uploadContentType(new File(['x'], 'a.heic', { type: 'image/jpg' }))).toBe('image/jpg')
  })
  it('upper-case extension', () => {
    expect(uploadContentType(new File(['x'], 'IMG_1.HEIC', { type: '' }))).toBe('image/heic')
  })
  it('unknown or missing extension is octet-stream', () => {
    expect(uploadContentType(new File(['x'], 'a.xyz', { type: '' }))).toBe('application/octet-stream')
    expect(uploadContentType(new File(['x'], 'noext', { type: '' }))).toBe('application/octet-stream')
  })
})

describe('each upload client sends a typeless .heic as image/heic', () => {
  const realFetch = global.fetch
  let puts: Array<RequestInit> = []
  beforeEach(() => {
    puts = []
    global.fetch = jest.fn(async (url: string, init: RequestInit = {}) => {
      if (init.method === 'PUT') puts.push(init)
      return { ok: true, status: 200, json: async () => ({
        upload_url: 'https://storage.test/put?t=1', storage_path: 'p/1', id: 1, attachments: [], module: {}, to_do: 0,
      }) }
    }) as unknown as typeof global.fetch
  })
  afterEach(() => { global.fetch = realFetch })
  const heic = () => new File(['h'], 'IMG_0001.HEIC', { type: '' })
  const sent = () => (puts[0].headers as Record<string, string>)['Content-Type']

  it('documents.ts', async () => {
    await uploadFileToSignedUrl('https://storage.test/put', heic())
    expect(sent()).toBe('image/heic')
  })
  it('requests.ts', async () => {
    await uploadOrgRequestAttachment(1, heic(), { token: 't' })
    expect(sent()).toBe('image/heic')
  })
  it('development.ts', async () => {
    await uploadLessonFile(1, 2, heic(), { token: 't' })
    expect(sent()).toBe('image/heic')
  })
  it('bursaryGrowth.ts', async () => {
    await sendTaskFile(1, heic(), { token: 't' })
    expect(sent()).toBe('image/heic')
  })
})
