import {
  shouldShowCoach, fallbackKeyFor, HELP_VERDICTS,
  helpSignal, readHelpCache, writeHelpCache, type StorageLike, type CachedHelp,
} from '@/lib/documentHelp'
import type { ApplicantDocument } from '@/lib/api'

/** Map-backed fake of the small Storage surface the cache uses (node env, no DOM). */
function fakeStorage(): StorageLike & { map: Map<string, string> } {
  const map = new Map<string, string>()
  return { map, getItem: (k) => map.get(k) ?? null, setItem: (k, v) => { map.set(k, v) } }
}

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

  it('shows the coach for a results slip that read uncertain, not for a clean one', () => {
    const slip = (results: string) =>
      doc({ doc_type: 'results_slip',
        academic_check: { name: 'match', subjects: 'match', results } } as Partial<ApplicantDocument>)
    expect(shouldShowCoach(slip('uncertain'))).toBe(true)   // a grade we couldn't be sure of
    expect(shouldShowCoach(slip('mismatch'))).toBe(true)
    expect(shouldShowCoach(slip('match'))).toBe(false)      // clean read → no coach (incl. a clean rotated slip)
  })

  it('falls back to deterministic presence checks when doc-assist did not run', () => {
    expect(shouldShowCoach(doc({ vision_name_match: 'not_found' }))).toBe(true)
    expect(shouldShowCoach(doc({ vision_name_match: 'found', vision_address_match: 'not_found' }))).toBe(true)
    expect(shouldShowCoach(doc({ vision_name_match: 'found' }))).toBe(false)
  })

  it('income IC anchors the cluster coach: shows iff cluster_status is non-empty', () => {
    const icDoc = (cluster_status: string) =>
      doc({ doc_type: 'parent_ic', vision_run_at: '2026-06-05T00:00:00Z',
        income_ic_check: { nric: '', name: 'X', address: '', member: 'father',
          name_status: 'match', readable: true, cluster_status } } as Partial<ApplicantDocument>)
    expect(shouldShowCoach(icDoc(''))).toBe(false)                         // consistent cluster → quiet
    expect(shouldShowCoach(icDoc('income_proof_person_mismatch'))).toBe(true)
    expect(shouldShowCoach(icDoc('income_relationship_mismatch'))).toBe(true)
  })

  it('income proof coaches ONLY when the member IC is missing (no second Gopal)', () => {
    const proof = (ic_present: boolean) =>
      doc({ doc_type: 'salary_slip',
        income_proof_check: { name: 'X', nric: '', amount: '', period: '', member: 'father',
          name_status: 'match', nric_status: 'no_ref', ic_present } } as Partial<ApplicantDocument>)
    expect(shouldShowCoach(proof(false))).toBe(true)   // no IC yet → "add the IC" nudge
    expect(shouldShowCoach(proof(true))).toBe(false)   // IC present → the IC anchors the coach
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

describe('helpSignal + advice cache (Gopal sticks, only re-fires after a re-upload)', () => {
  const aiHelp: CachedHelp = { source: 'ai', message: 'Try a clearer photo.', verdict: 'nric_mismatch' }

  it('signal changes only when verdict-relevant state changes', () => {
    const base = doc({ vision_run_at: 't1', vision_name_match: 'not_found' })
    expect(helpSignal(base)).toBe(helpSignal(doc({ vision_run_at: 't1', vision_name_match: 'not_found' })))
    // a re-upload (new vision_run_at) changes the signal → cache miss → Gopal re-fires
    expect(helpSignal(base)).not.toBe(helpSignal(doc({ vision_run_at: 't2', vision_name_match: 'not_found' })))
  })

  it('round-trips cached advice for the same signal (reload reuses it, no re-fetch)', () => {
    const s = fakeStorage()
    writeHelpCache(7, 'sig-A', aiHelp, s)
    expect(readHelpCache(7, 'sig-A', s)).toEqual(aiHelp)
  })

  it('misses on a different signal (a re-upload) and a different doc', () => {
    const s = fakeStorage()
    writeHelpCache(7, 'sig-A', aiHelp, s)
    expect(readHelpCache(7, 'sig-B', s)).toBeNull()   // signal changed → re-fire
    expect(readHelpCache(8, 'sig-A', s)).toBeNull()   // different document
  })

  it('is safe when storage is unavailable (SSR / disabled)', () => {
    expect(readHelpCache(7, 'sig-A', null)).toBeNull()
    expect(() => writeHelpCache(7, 'sig-A', aiHelp, null)).not.toThrow()
  })

  it('ignores corrupt / bad-shaped cache entries', () => {
    const s = fakeStorage()
    s.map.set('halatuju_doc_help_7_sig-A', '{not json')
    expect(readHelpCache(7, 'sig-A', s)).toBeNull()
    s.map.set('halatuju_doc_help_7_sig-B', JSON.stringify({ source: 'bogus' }))
    expect(readHelpCache(7, 'sig-B', s)).toBeNull()
  })
})
