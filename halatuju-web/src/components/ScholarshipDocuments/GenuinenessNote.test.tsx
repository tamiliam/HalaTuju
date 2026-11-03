/**
 * @jest-environment jsdom
 *
 * Matric/Diploma M4b (owner rulings 2026-10-29) — the student's note on a higher-results upload the
 * owner ruled is not the results asked for: a semester result slip or the polytechnic student portal
 * — any page that is not the final result (ruling B) — asks for the final academic transcript; a
 * Matriculation offer letter is not a results document;
 * every other non-genuine document keeps the general note. `t` echoes its key.
 *
 * drift-test: the `doc_seen` codes and `final_owed` are the backend's own (`genuineness/matric_poly_doc.py`,
 * `genuineness/bands.py`), read below.
 */
import { render, screen } from '@testing-library/react'
import { GenuinenessNote, genuinenessNoteKey } from './checklists'
import type { ApplicantDocument } from '@/lib/api'
import { readApi } from '@/test/apiSource'
import enMessages from '@/messages/en.json'
import msMessages from '@/messages/ms.json'
import taMessages from '@/messages/ta.json'

const t = (key: string) => key

function doc(status: string, doc_seen: string): ApplicantDocument {
  return { id: 1, doc_type: 'higher_results', authenticity: { status, reason: '', doc_seen } } as unknown as ApplicantDocument
}

describe('GenuinenessNote — the owner-ruled higher-results pages (M4b)', () => {
  test.each(['matric_result_slip', 'poly_result_slip', 'poly_portal_page', 'matric_transcript_not_final',
    'poly_transcript_not_final'])('%s asks for the final transcript', (seen) => {
    render(<GenuinenessNote doc={doc('final_owed', seen)} t={t} />)
    expect(screen.getByText('scholarship.docs.genuineness.askFinal')).toBeTruthy()
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
    for (const code of ['matric_result_slip', 'poly_result_slip', 'poly_portal_page', 'matric_offer_letter',
      'matric_transcript_not_final', 'poly_transcript_not_final']) {
      expect(src).toContain(`'${code}'`)
    }
    expect(readApi('apps/scholarship/genuineness/bands.py')).toContain("FINAL_OWED = 'final_owed'")
  })
})

describe('GenuinenessNote — an offer letter (offer exact-read S6, owner rulings 2026-11-01)', () => {
  const offer = (status: string) =>
    ({ id: 2, doc_type: 'offer_letter', authenticity: { status, reason: '', doc_seen: 'ua_offer' } }) as unknown as ApplicantDocument
  test('a SUSPECT offer says "not an offer letter — upload yours if you have it" (never a blocker)', () => {
    render(<GenuinenessNote doc={offer('suspect')} t={t} />)
    expect(screen.getByText('scholarship.docs.genuineness.offerSuspect')).toBeTruthy()
  })
  test('a not_offer_letter offer gets the fail note, never "nothing is blocked"', () => {
    render(<GenuinenessNote doc={offer('not_offer_letter')} t={t} />)
    expect(screen.getByText('scholarship.docs.genuineness.offerNotOffer')).toBeTruthy()
  })
  test('a genuine offer shows no note', () => {
    const { container } = render(<GenuinenessNote doc={offer('genuine')} t={t} />)
    expect(container.textContent).toBe('')
  })
  test('the two notes exist in en / ms / ta, and only the suspect one says nothing is blocked', () => {
    for (const [m, blocked] of [[enMessages, 'Nothing is blocked'], [msMessages, 'Tiada apa-apa disekat'],
                                [taMessages, 'எதுவும் தடுக்கப்படவில்லை']] as const) {
      const g = m.scholarship.docs.genuineness
      expect(g.offerSuspect).toContain(blocked)
      expect(g.offerNotOffer).toBeTruthy()
      expect(g.offerNotOffer).not.toContain(blocked)
    }
  })
})
