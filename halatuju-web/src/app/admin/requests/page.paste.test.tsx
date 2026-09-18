/**
 * @jest-environment jsdom
 *
 * SCREENSHOT PASTE ON THE REQUEST **CREATE** FORM — the second surface, mounted.
 *
 * ⚠ WHY THIS FILE EXISTS. Paste and drag-and-drop shipped on 2026-07-30 into the request DETAIL
 * page only, and the owner had to report the same missing feature twice — on the surface where a
 * screenshot most naturally starts life: you take it, then you describe the bug. The mistake was
 * one of SCOPE, so `screenshotInput.test.ts` still walks the disk to prove no surface was
 * forgotten. But every claim about what a paste actually DOES now belongs here, because a
 * source-shape check cannot see focus — and that is not hypothetical: the first version of that
 * guard asserted `onPaste=` was attached, went green, and the feature was dead on both surfaces,
 * because a paste is dispatched at the FOCUSED element and bubbles UPWARD, and the handler sat on
 * an unfocusable <div> nothing could ever reach.
 *
 * So the paste below is dispatched from the DESCRIBE box — where a person is actually typing —
 * and never at the drop zone itself. A test that dispatched at the panel would pass under both
 * implementations and prove nothing.
 *
 * This form STAGES `File` objects rather than uploading (there is no request id until the request
 * exists), so the assertion is the staged thumbnail, not an api call.
 */
import { act, render, screen, waitFor } from '@testing-library/react'

import AdminRequestsPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
/** The signed-in role, mutable between mounts — the AppShell.test.tsx pattern. Only an
 *  `org_admin` gets the submit form, and only the submit form gets a paste listener. */
let mockRole: Record<string, unknown> = { role: 'org_admin', is_super_admin: false }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'test-token', role: mockRole }),
}))

const mockApi = api as jest.Mocked<typeof api>

/** jsdom has no clipboard, so the event is built by hand — `files` is what the handler reads. */
function pasteEvent(files: File[]): Event {
  const e = new Event('paste', { bubbles: true, cancelable: true })
  Object.defineProperty(e, 'clipboardData', { value: { files } })
  return e
}

const png = (name = '') => new File([new Uint8Array([1, 2, 3])], name, { type: 'image/png' })

/** jsdom implements no object URLs; the staged thumbnail asks for one on every render. */
const originalCreateObjectURL = URL.createObjectURL

beforeAll(() => {
  URL.createObjectURL = () => 'blob:test'
})
afterAll(() => {
  URL.createObjectURL = originalCreateObjectURL
})

beforeEach(() => {
  jest.clearAllMocks()
  mockRole = { role: 'org_admin', is_super_admin: false }
  mockApi.getOrgRequests.mockResolvedValue({ requests: [] })
})

/** The form has arrived, and so has the drop zone the paste stages into. */
const mounted = async () => {
  render(<AdminRequestsPage />)
  await screen.findByText('admin.requests.attachments.dropZone')
}

describe('pasting a screenshot into the request form', () => {
  it('stages an image pasted while typing the description', async () => {
    await mounted()
    const describe_ = screen.getByPlaceholderText('admin.requests.form.descriptionPlaceholder')
    describe_.focus()
    await act(async () => { describe_.dispatchEvent(pasteEvent([png()])) })

    // The success state: a thumbnail, captioned with a name the clipboard did not supply.
    await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(1))
    expect(screen.getByRole('img').getAttribute('alt')).toMatch(/^screenshot-\d+\.png$/)
  })

  it('⚠ LEAVES A TEXT PASTE COMPLETELY ALONE', async () => {
    // The price of listening document-wide: Ctrl+V into any field must be untouched, so the
    // handler bails on a fileless clipboard BEFORE it calls preventDefault.
    await mounted()
    const e = pasteEvent([])
    await act(async () => { document.body.dispatchEvent(e) })
    expect(e.defaultPrevented).toBe(false)
    expect(screen.queryAllByRole('img')).toHaveLength(0)
  })

  it('ignores a pasted PDF, and does not swallow the event either', async () => {
    await mounted()
    const e = pasteEvent([new File([new Uint8Array([1])], 'notes.pdf',
                                   { type: 'application/pdf' })])
    await act(async () => { document.body.dispatchEvent(e) })
    expect(e.defaultPrevented).toBe(false)
    expect(screen.queryAllByRole('img')).toHaveLength(0)
  })

  it('stops listening once the form is left', async () => {
    const { unmount } = render(<AdminRequestsPage />)
    await screen.findByText('admin.requests.attachments.dropZone')
    unmount()
    await act(async () => { document.body.dispatchEvent(pasteEvent([png()])) })
    expect(screen.queryAllByRole('img')).toHaveLength(0)
  })
})

describe('the drop zone is a target before the drag begins', () => {
  it('is on screen, and says what you can do with it', async () => {
    // The third shape of the same mistake: the handler fired, but there was nothing on screen to
    // aim a drag at — a text link plus copy promising paste and drag, with the wrapper collapsing
    // to the height of the link. The owner asked whether a surface had been built at all.
    await mounted()
    // Written as `+ {t(…)}`, so the label is two text nodes — matched on the key alone.
    expect(screen.getByText(/admin\.requests\.attachments\.add/)).toBeTruthy()
    expect(screen.getByText('admin.requests.attachments.dropZone')).toBeTruthy()
    expect(screen.getByText('admin.requests.attachments.hint')).toBeTruthy()
  })

  it('accepts a DROP, which is the other half of the promise', async () => {
    await mounted()
    const zone = screen.getByText('admin.requests.attachments.dropZone')
      .closest('label') as HTMLElement
    await act(async () => {
      const e = new Event('drop', { bubbles: true, cancelable: true })
      Object.defineProperty(e, 'dataTransfer', { value: { files: [png('shot.png')] } })
      zone.dispatchEvent(e)
    })
    await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(1))
    expect(screen.getByRole('img').getAttribute('alt')).toBe('shot.png')
  })
})

describe('only the person who may submit gets a paste listener', () => {
  it('a super sees the list but no form, so a paste stages nothing', async () => {
    // The listener is wired to `isOrgAdmin` — the same gate as the form. A document-wide handler
    // on a page with nowhere to put the file would swallow the paste for no reason.
    mockRole = { role: 'super', is_super_admin: true }
    render(<AdminRequestsPage />)
    await waitFor(() => expect(mockApi.getOrgRequests).toHaveBeenCalled())
    expect(screen.queryByText('admin.requests.attachments.dropZone')).toBeNull()

    const e = pasteEvent([png()])
    await act(async () => { document.body.dispatchEvent(e) })
    expect(e.defaultPrevented).toBe(false)
  })
})
