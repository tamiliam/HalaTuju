/**
 * THE DRIFT TEST for the early upload refusal in `uploadCheck.ts` — named by its `drift-test:` marker.
 *
 * The browser refuses, before uploading, a file the server's `_is_allowed_upload` would refuse (TD-080):
 * an image or a PDF by type, else by extension. Mobile M4 moved the rule into this leaf so the Action
 * Centre uses it too. Both directions are read from the server's own source, never restated here: every
 * extension the server accepts the browser accepts, and the browser accepts no extension the server
 * would refuse — a stricter browser blocks a good file, a looser one wastes an upload on a refusal.
 */
import { isAcceptedUpload } from '@/lib/uploadCheck'
import { readApi } from '@/test/apiSource'

const VIEWS = 'apps/scholarship/views.py'
const src = readApi(VIEWS)

const serverExts = (() => {
  const m = src.match(/_ALLOWED_UPLOAD_EXTENSIONS = frozenset\(\{([^}]*)\}\)/)
  if (!m) throw new Error(`drift test: no _ALLOWED_UPLOAD_EXTENSIONS in ${VIEWS} — the allowlist moved; follow it`)
  return Array.from(m[1].matchAll(/'\.(\w+)'/g), (x) => x[1])
})()

const typeless = (ext: string) => new File(['x'], `doc.${ext}`, { type: '' })

it('the server allowlist is really there', () => {
  expect(serverExts.length).toBeGreaterThanOrEqual(8)
  expect(src).toMatch(/ct\.startswith\('image\/'\) or ct == 'application\/pdf'/)
})

it('every extension the server accepts, the browser accepts (no type to lean on)', () => {
  for (const ext of serverExts) expect([ext, isAcceptedUpload(typeless(ext))]).toEqual([ext, true])
})

it('the browser accepts no extension the server would refuse', () => {
  for (const ext of ['mp4', 'mov', 'docx', 'zip', 'txt', 'exe', 'svg']) {
    expect(serverExts).not.toContain(ext)
    expect([ext, isAcceptedUpload(typeless(ext))]).toEqual([ext, false])
  }
})

it('by type, both accept any image and a PDF, and neither a video', () => {
  expect(isAcceptedUpload(new File(['x'], 'a', { type: 'image/heic' }))).toBe(true)
  expect(isAcceptedUpload(new File(['x'], 'a', { type: 'application/pdf' }))).toBe(true)
  expect(isAcceptedUpload(new File(['x'], 'a', { type: 'video/mp4' }))).toBe(false)
})
