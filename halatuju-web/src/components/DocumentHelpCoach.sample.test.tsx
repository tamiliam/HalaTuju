/**
 * @jest-environment jsdom
 *
 * H9: the coach shows "See a sample" where a sample helps the student fix the upload (wrong kind of
 * document, unreadable, a skewed slip, a stale STR) and not on a verdict that has nothing to show (a name
 * mismatch, a sample upload) or on a good document. The button opens the H8 viewer. Real English words.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import DocumentHelpCoach from './DocumentHelpCoach'
import * as api from '@/lib/api'
import type { ApplicantDocument } from '@/lib/api'
import { interpolateMessage } from '@/lib/branding'
import { shouldShowCoach, wantsSample } from '@/lib/documentHelp'
import en from '@/messages/en.json'

const lookup = (key: string, params?: Record<string, string>): string => {
  const value = key.split('.').reduce<unknown>(
    (node, part) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[part] : undefined), en)
  return typeof value === 'string' ? interpolateMessage(value, params) : key
}

jest.mock('@/lib/api', () => ({ __esModule: true, ...jest.requireActual('@/lib/api'), getDocumentHelp: jest.fn() }))
jest.mock('@/lib/i18n', () => ({ ...jest.requireActual('@/lib/i18n'), useT: () => ({ t: lookup, locale: 'en' }) }))
jest.mock('next/link', () => ({ __esModule: true, default: ({ children, ...p }: { children: React.ReactNode }) => <a {...p}>{children}</a> }))

const mockApi = api as jest.Mocked<typeof api>

let nextId = 100
function doc(over: Partial<ApplicantDocument> = {}): ApplicantDocument {
  return {
    id: nextId++, doc_type: 'salary_slip', original_filename: 'x', content_type: '', size: 0,
    verification_status: 'pending', uploaded_at: '', download_url: null, vision_nric: '', vision_name: '',
    vision_run_at: '2026-11-01T09:00:00Z', vision_error: '', vision_nric_verdict: '', vision_name_verdict: '',
    vision_name_match: '', vision_address_match: '', vision_fields: { student_verdict: 'wrong_doc' },
    ...over,
  } as ApplicantDocument
}

function serve(verdict: string) {
  mockApi.getDocumentHelp.mockResolvedValue(
    { source: 'none', message: '', verdict } as unknown as Awaited<ReturnType<typeof api.getDocumentHelp>>)
  // 'none' hides the coach; the fallback is what the student sees with the AI off.
  mockApi.getDocumentHelp.mockResolvedValue(
    { source: 'fallback', message: '', verdict } as unknown as Awaited<ReturnType<typeof api.getDocumentHelp>>)
}

const mount = (d: ApplicantDocument) =>
  render(<DocumentHelpCoach doc={d} token="t" t={lookup} lang="en" />)

describe('the coach and "See a sample"', () => {
  beforeEach(() => { window.localStorage.clear(); mockApi.getDocumentHelp.mockReset() })

  it.each(['wrong_doc', 'unreadable', 'slip_skewed_unclear', 'str_not_current'])(
    'shows the button on %s and it opens the viewer', async (verdict) => {
      serve(verdict)
      mount(doc())
      const btn = await screen.findByText('See a sample')
      expect(screen.queryByTestId('sample-viewer')).toBeNull()
      fireEvent.click(btn)
      expect(screen.getByTestId('sample-viewer')).toBeTruthy()
      expect(screen.getByRole('img').getAttribute('src')).toMatch(/^\/samples\//)
    })

  it.each(['name_mismatch', 'sample_document', 'review_manually'])('no button on %s', async (verdict) => {
    serve(verdict)
    mount(doc())
    await waitFor(() => expect(mockApi.getDocumentHelp).toHaveBeenCalled())
    await waitFor(() => expect(document.body.textContent).toContain('Helper'))
    expect(screen.queryByText('See a sample')).toBeNull()
  })

  it('a good document has no coach and so no button', () => {
    const good = doc({ vision_fields: { student_verdict: 'ok' } })
    expect(shouldShowCoach(good)).toBe(false)
    mount(good)
    expect(screen.queryByText('See a sample')).toBeNull()
    expect(mockApi.getDocumentHelp).not.toHaveBeenCalled()
  })

  it('a sample upload is coached, with the plain message', async () => {
    const sample = doc({ vision_fields: { authenticity: { status: 'not_salary_slip', doc_seen: 'sample_document', sample: true } } })
    expect(shouldShowCoach(sample)).toBe(true)
    serve('sample_document')
    mount(sample)
    expect(await screen.findByText('This looks like a sample, not your real document. Please upload your own.')).toBeTruthy()
  })

  it('wantsSample covers exactly the chosen verdicts', () => {
    expect(wantsSample('wrong_doc')).toBe(true)
    expect(wantsSample('')).toBe(false)
    expect(wantsSample('name_mismatch')).toBe(false)
  })
})
