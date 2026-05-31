import { shouldShowCoach, fallbackKeyFor, HELP_VERDICTS } from '@/lib/documentHelp'
import type { ApplicantDocument } from '@/lib/api'

// Minimal doc factory — only the fields shouldShowCoach reads.
function doc(over: Partial<ApplicantDocument> = {}): ApplicantDocument {
  return {
    id: 1, doc_type: 'salary_slip', original_filename: 'x', content_type: '', size: 0,
    verification_status: 'pending', uploaded_at: '', download_url: null,
    vision_nric: '', vision_name: '', vision_run_at: null, vision_error: '',
    vision_nric_verdict: '', vision_name_verdict: '',
    vision_name_match: '', vision_address_match: '',
    ...over,
  } as ApplicantDocument
}

describe('shouldShowCoach', () => {
  it('is false for an unchecked doc', () => {
    expect(shouldShowCoach(doc())).toBe(false)
  })

  it('is false for a good supporting verdict', () => {
    expect(shouldShowCoach(doc({ vision_fields: { student_verdict: 'ok' } }))).toBe(false)
  })

  it('is true for each non-good supporting verdict', () => {
    for (const v of ['name_mismatch', 'address_mismatch', 'wrong_doc', 'unreadable', 'review_manually'] as const) {
      expect(shouldShowCoach(doc({ vision_fields: { student_verdict: v } }))).toBe(true)
    }
  })

  it('is false for a clean IC (nric match), true for nric/name/unreadable problems', () => {
    const ran = { vision_run_at: '2026-05-31T00:00:00Z', doc_type: 'ic' }
    expect(shouldShowCoach(doc({ ...ran, vision_nric_verdict: 'match', vision_name_verdict: 'partial' }))).toBe(false)
    expect(shouldShowCoach(doc({ ...ran, vision_nric_verdict: 'mismatch' }))).toBe(true)
    expect(shouldShowCoach(doc({ ...ran, vision_nric_verdict: 'match', vision_name_verdict: 'mismatch' }))).toBe(true)
    expect(shouldShowCoach(doc({ ...ran, vision_nric_verdict: 'unreadable' }))).toBe(true)
  })

  it('ignores IC verdicts before Vision has run', () => {
    expect(shouldShowCoach(doc({ doc_type: 'ic', vision_nric_verdict: 'mismatch', vision_run_at: null }))).toBe(false)
  })

  it('falls back to deterministic presence checks when doc-assist did not run', () => {
    expect(shouldShowCoach(doc({ vision_name_match: 'not_found' }))).toBe(true)
    expect(shouldShowCoach(doc({ vision_name_match: 'found', vision_address_match: 'not_found' }))).toBe(true)
    expect(shouldShowCoach(doc({ vision_name_match: 'found' }))).toBe(false)
  })
})

describe('fallbackKeyFor', () => {
  it('maps each known verdict to its namespaced key', () => {
    for (const v of HELP_VERDICTS) {
      expect(fallbackKeyFor(v)).toBe(`scholarship.docs.help.fallback.${v}`)
    }
  })

  it('defaults unknown/undefined to the generic warm copy', () => {
    expect(fallbackKeyFor(undefined)).toBe('scholarship.docs.help.fallback.generic')
    expect(fallbackKeyFor('weird')).toBe('scholarship.docs.help.fallback.generic')
  })
})
