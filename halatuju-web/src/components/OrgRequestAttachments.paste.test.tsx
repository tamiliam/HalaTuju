/**
 * @jest-environment jsdom
 *
 * Screenshot PASTE, tested by dispatching one — the behaviour a source-shape test cannot see.
 *
 * `screenshotInput.test.ts` reads these files as TEXT. That is the right tool for structural claims
 * ("no surface was forgotten", "the dead path is gone") and it was the WRONG tool for this: it
 * asserted `/onPaste=/`, went green, and the feature was dead on both surfaces for a day.
 *
 * Why it was dead, and what this file therefore has to reproduce: a paste event is dispatched at the
 * FOCUSED element and bubbles UPWARD. `onPaste` sat on the screenshot <div>, which is not focusable
 * and contains nothing focusable — so no real paste was ever on a path that reached it. The fix
 * listens on the document.
 *
 * So the test below **dispatches from somewhere else on the page**, which is the whole point. A test
 * that dispatched at the panel itself would pass under both implementations and prove nothing.
 */
import { act, render, waitFor } from '@testing-library/react'

import OrgRequestAttachments from './OrgRequestAttachments'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-api')
jest.mock('@/components/DocViewer', () => ({
  __esModule: true,
  default: () => null,
}))

const mockApi = api as jest.Mocked<typeof api>

/**
 * jsdom has no clipboard, so build the event by hand. `files` is what both handlers read; a text
 * paste is modelled as the same event with an empty list, which is exactly how a real one arrives.
 */
function pasteEvent(files: File[]): Event {
  const e = new Event('paste', { bubbles: true, cancelable: true })
  Object.defineProperty(e, 'clipboardData', { value: { files } })
  return e
}

const png = (name = '') => new File([new Uint8Array([1, 2, 3])], name, { type: 'image/png' })

const props = () => ({
  requestId: 7,
  attachments: [],
  editable: true,
  token: 'tok',
  onChange: jest.fn(),
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.uploadOrgRequestAttachment.mockResolvedValue({ id: 7 } as unknown as api.OrgRequestDetail)
})

describe('pasting a screenshot into the request detail page', () => {
  it('uploads an image pasted while focus is ELSEWHERE on the page', async () => {
    // The scenario that was broken: you are not clicked into the screenshot panel — nobody ever is,
    // it has nothing focusable in it — you simply press Ctrl+V after taking the screenshot.
    const outside = document.createElement('textarea')
    document.body.appendChild(outside)
    render(<OrgRequestAttachments {...props()} />)

    outside.focus()
    await act(async () => { outside.dispatchEvent(pasteEvent([png()])) })

    await waitFor(() => expect(mockApi.uploadOrgRequestAttachment).toHaveBeenCalledTimes(1))
    const [id, file] = mockApi.uploadOrgRequestAttachment.mock.calls[0]
    expect(id).toBe(7)
    expect((file as File).name).toMatch(/^screenshot-\d+\.png$/)   // a pasted file arrives nameless
  })

  it('ignores a paste carrying no files, so typing Ctrl+V stays normal', async () => {
    render(<OrgRequestAttachments {...props()} />)

    const e = pasteEvent([])
    await act(async () => { document.body.dispatchEvent(e) })

    await Promise.resolve()
    expect(mockApi.uploadOrgRequestAttachment).not.toHaveBeenCalled()
    expect(e.defaultPrevented).toBe(false)   // never swallow a text paste
  })

  it('ignores a non-image paste — a dragged PDF or copied file', async () => {
    render(<OrgRequestAttachments {...props()} />)

    const pdf = new File([new Uint8Array([1])], 'notes.pdf', { type: 'application/pdf' })
    await act(async () => { document.body.dispatchEvent(pasteEvent([pdf])) })

    await Promise.resolve()
    expect(mockApi.uploadOrgRequestAttachment).not.toHaveBeenCalled()
  })

  it('does NOT listen while the request is closed to changes', async () => {
    // editable=false is how an accepted or terminal request renders (canAttach).
    render(<OrgRequestAttachments {...props()} editable={false} />)

    await act(async () => { document.body.dispatchEvent(pasteEvent([png()])) })

    await Promise.resolve()
    expect(mockApi.uploadOrgRequestAttachment).not.toHaveBeenCalled()
  })

  it('stops listening once unmounted — no upload from a page you have left', async () => {
    const { unmount } = render(<OrgRequestAttachments {...props()} />)
    unmount()

    await act(async () => { document.body.dispatchEvent(pasteEvent([png()])) })

    await Promise.resolve()
    expect(mockApi.uploadOrgRequestAttachment).not.toHaveBeenCalled()
  })

  it('handles ONE paste once — the dead div handler must not linger beside the live one', async () => {
    const outside = document.createElement('textarea')
    document.body.appendChild(outside)
    render(<OrgRequestAttachments {...props()} />)

    outside.focus()
    await act(async () => { outside.dispatchEvent(pasteEvent([png()])) })

    await waitFor(() => expect(mockApi.uploadOrgRequestAttachment).toHaveBeenCalled())
    // Two handlers on the same bubbling path would upload the same image twice.
    expect(mockApi.uploadOrgRequestAttachment).toHaveBeenCalledTimes(1)
  })
})
