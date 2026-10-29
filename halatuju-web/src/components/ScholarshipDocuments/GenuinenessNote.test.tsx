/**
 * @jest-environment jsdom
 *
 * Matric/Diploma M4b (owner rulings 2026-10-29) — the student's note on a higher-results upload the
 * owner ruled is not the results asked for: a semester result slip or the polytechnic student portal
 * asks for the full academic transcript; a Matriculation offer letter is not a results document;
 * every other non-genuine document keeps the general note. `t` echoes its key.
 *
 * drift-test: the `doc_seen` codes are the backend's own (`genuineness/matric_poly_doc.py`), read below.
 */
import { render, screen } from '@testing-library/react'
import { GenuinenessNote, genuinenessNoteKey } from './checklists'
import type { ApplicantDocument } from '@/lib/api'
import { readApi } from '@/test/apiSource'

const t = (key: string) => key

function doc(status: string, doc_seen: string): ApplicantDocument {
  return { id: 1, doc_type: 'higher_results', authenticity: { status, reason: '', doc_seen } } as unknown as ApplicantDocument
}

describe('GenuinenessNote — the owner-ruled higher-results pages (M4b)', () => {
  test.each(['matric_result_slip', 'poly_result_slip', 'poly_portal_page'])('%s asks for the full transcript', (seen) => {
    render(<GenuinenessNote doc={doc('not_higher_results', seen)} t={t} />)
    expect(screen.getByText('scholarship.docs.genuineness.askTranscript')).toBeTruthy()
  })

  test('an offer letter is not a results document', () => {
    render(<GenuinenessNote doc={doc('not_higher_results', 'matric_offer_letter')} t={t} />)
    expect(screen.getByText('scholarship.docs.genuineness.notResults')).toBeTruthy()
  })

  test('every other non-genuine document keeps the general note; a genuine one shows none', () => {
    expect(genuinenessNoteKey('stpm_online_results_page')).toBe('scholarship.docs.genuineness.note')
    expect(genuinenessNoteKey(undefined)).toBe('scholarship.docs.genuineness.note')
    const { container } = render(<GenuinenessNote doc={doc('genuine', 'matric_transcript')} t={t} />)
    expect(container.textContent).toBe('')
  })

  test('the codes are the backend\'s own', () => {
    const src = readApi('apps/scholarship/genuineness/matric_poly_doc.py')
    for (const code of ['matric_result_slip', 'poly_result_slip', 'poly_portal_page', 'matric_offer_letter']) {
      expect(src).toContain(`'${code}'`)
    }
  })
})
