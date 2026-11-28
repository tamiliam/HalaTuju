/**
 * Owner ruling 28 Nov 2026: the cockpit's clear-accept reads the SERVER's hand-off, never
 * `completeness.complete`. Case 513 is the shape: submitted, interviewing, quiz wiped by bug #81.
 */
import { handoffMissing, handoffReady } from '@/lib/handoff'
import { isClearAccept, verdictSaveOutcome } from '@/lib/officerCockpit'

const ALL_DONE = {
  quiz_done: true, details_done: true, funding_done: true, documents_done: true, consent_done: true,
  address_done: true, guardian_docs_done: true, family_done: true, complete: true,
}
const QUIZ_GONE = { ...ALL_DONE, quiz_done: false, complete: false }

describe('handoffReady', () => {
  it('case 513: the served hand-off is ready while completeness says incomplete', () => {
    const d = { completeness: QUIZ_GONE, handoff: { ready: true, missing: [] } }
    expect(handoffReady(d)).toBe(true)
    expect(isClearAccept(handoffReady(d), 'interviewing')).toBe(true)
    expect(verdictSaveOutcome({
      acceptRequested: true, accepted: false, handoffReady: handoffReady(d), status: 'interviewing',
    })).toBe('saved')   // allowed — the submit runs, so the line is not "not sent to QC"
  })

  it('a served not-ready wins over a complete completeness', () => {
    const d = { completeness: ALL_DONE, handoff: { ready: false, missing: ['consent_done'] } }
    expect(handoffReady(d)).toBe(false)
    expect(isClearAccept(handoffReady(d), 'interviewing')).toBe(false)
  })

  it('an older api with no handoff falls back to the served completeness answer', () => {
    expect(handoffReady({ completeness: ALL_DONE })).toBe(true)
    expect(handoffReady({ completeness: QUIZ_GONE })).toBe(false)
    expect(handoffReady(null)).toBe(false)
    expect(handoffReady({})).toBe(false)
  })
})

describe('handoffMissing', () => {
  it('reads the served list, not the false completeness parts', () => {
    const d = { completeness: { ...QUIZ_GONE, consent_done: false }, handoff: { ready: false, missing: ['consent_done'] } }
    expect(handoffMissing(d)).toEqual(['consent_done'])
  })

  it('is empty when the hand-off is ready, whatever completeness says', () => {
    expect(handoffMissing({ completeness: QUIZ_GONE, handoff: { ready: true, missing: [] } })).toEqual([])
  })

  it('falls back to the false completeness parts on an older api', () => {
    expect(handoffMissing({ completeness: QUIZ_GONE })).toEqual(['quiz_done'])
    expect(handoffMissing(undefined)).toEqual([])
  })

  it('returns a copy, so a caller cannot change the served list', () => {
    const missing = ['documents_done']
    const out = handoffMissing({ handoff: { ready: false, missing } })
    out.push('x')
    expect(missing).toEqual(['documents_done'])
  })
})
