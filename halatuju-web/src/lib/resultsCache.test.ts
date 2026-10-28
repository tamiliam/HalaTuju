/**
 * @jest-environment node
 *
 * The rule these pin: "not in this browser's cache" must never be reported as "you have no
 * profile". Org request #11 (2026-08-13) — a shortlisted Form 6 applicant was shown *No profile
 * found. Please complete the onboarding.* on a record that had completed it.
 */
import { resolveCachedResults, type ReadableStore } from './resultsCache'
import {
  KEY_ALIRAN, KEY_EXAM_TYPE, KEY_GRADES, KEY_MERIT, KEY_MUET_BAND, KEY_PROFILE,
  KEY_SPM_PREREQ, KEY_STPM_CGPA, KEY_STPM_GRADES, KEY_HIGHER_CGPA, KEY_HIGHER_KOKO,
} from './storage'

function store(values: Record<string, string>): ReadableStore {
  return { getItem: (k: string) => (k in values ? values[k] : null) }
}

const SPM_GRADES = JSON.stringify({ bm: 'A', eng: 'B+', math: 'A-' })
const DEMOGRAPHICS = JSON.stringify({ gender: 'male', nationality: 'malaysian', coqScore: 7 })
const STPM_GRADES = JSON.stringify({ pa: 'A', math_t: 'B' })

describe('resolveCachedResults', () => {
  it('reads an SPM student from the cache', () => {
    const r = resolveCachedResults(store({
      [KEY_EXAM_TYPE]: 'spm', [KEY_GRADES]: SPM_GRADES, [KEY_PROFILE]: DEMOGRAPHICS,
      [KEY_MERIT]: '81.5', [KEY_ALIRAN]: JSON.stringify(['phy', 'chem']),
    }))
    expect(r.view).toBe('spm')
    if (r.view !== 'spm') throw new Error('narrowing')
    expect(r.profile.grades).toEqual({ bm: 'A', eng: 'B+', math: 'A-' })
    expect(r.profile.student_merit).toBe(81.5)
    expect(r.profile.stream_subjects).toEqual(['phy', 'chem'])
    expect(r.profile.coq_score).toBe(7)
  })

  it('reads a complete STPM student from the cache', () => {
    const r = resolveCachedResults(store({
      [KEY_EXAM_TYPE]: 'stpm', [KEY_PROFILE]: DEMOGRAPHICS,
      [KEY_STPM_GRADES]: STPM_GRADES, [KEY_STPM_CGPA]: '3.5', [KEY_MUET_BAND]: '4',
      [KEY_SPM_PREREQ]: SPM_GRADES,
    }))
    expect(r.view).toBe('stpm')
    if (r.view !== 'stpm') throw new Error('narrowing')
    expect(r.stpm.cgpa).toBe(3.5)
    expect(r.stpm.muetBand).toBe(4)
    expect(r.stpm.spmGrades).toEqual({ bm: 'A', eng: 'B+', math: 'A-' })
  })

  // ── THE BUG ────────────────────────────────────────────────────────────────────────────
  it('THE FORM 6 CASE: declared STPM, no STPM results, falls back to the SPM grades held', () => {
    const r = resolveCachedResults(store({
      [KEY_EXAM_TYPE]: 'stpm', [KEY_GRADES]: SPM_GRADES, [KEY_PROFILE]: DEMOGRAPHICS,
    }))
    expect(r.view).toBe('spm')          // NOT 'none' — this is what showed "No profile found"
  })

  it.each([
    ['no CGPA', { [KEY_STPM_GRADES]: STPM_GRADES, [KEY_MUET_BAND]: '4' }],
    ['no MUET band', { [KEY_STPM_GRADES]: STPM_GRADES, [KEY_STPM_CGPA]: '3.5' }],
    ['no grades', { [KEY_STPM_CGPA]: '3.5', [KEY_MUET_BAND]: '4' }],
    ['empty grades', { [KEY_STPM_GRADES]: '{}', [KEY_STPM_CGPA]: '3.5', [KEY_MUET_BAND]: '4' }],
  ])('a PARTIAL STPM set (%s) still falls back rather than scoring half an answer', (_label, partial) => {
    const r = resolveCachedResults(store({
      [KEY_EXAM_TYPE]: 'stpm', [KEY_GRADES]: SPM_GRADES, [KEY_PROFILE]: DEMOGRAPHICS,
      ...partial,
    }))
    expect(r.view).toBe('spm')
  })

  it('declared STPM with nothing to fall back to asks for the RESULTS, not for onboarding', () => {
    const r = resolveCachedResults(store({ [KEY_EXAM_TYPE]: 'stpm' }))
    expect(r.view).toBe('stpm_pending')
  })

  it('an empty browser reads as none — the caller must re-read, not conclude', () => {
    expect(resolveCachedResults(store({})).view).toBe('none')
  })

  it('malformed JSON is treated as absent and never throws', () => {
    expect(() => resolveCachedResults(store({
      [KEY_EXAM_TYPE]: 'spm', [KEY_GRADES]: '{not json', [KEY_PROFILE]: DEMOGRAPHICS,
    }))).not.toThrow()
    expect(resolveCachedResults(store({
      [KEY_EXAM_TYPE]: 'spm', [KEY_GRADES]: '{not json', [KEY_PROFILE]: DEMOGRAPHICS,
    })).view).toBe('none')
  })

  it('an empty SPM grades object is not a profile', () => {
    expect(resolveCachedResults(store({
      [KEY_GRADES]: '{}', [KEY_PROFILE]: DEMOGRAPHICS,
    })).view).toBe('none')
  })

  it('a missing exam type defaults to SPM', () => {
    expect(resolveCachedResults(store({
      [KEY_GRADES]: SPM_GRADES, [KEY_PROFILE]: DEMOGRAPHICS,
    })).view).toBe('spm')
  })

  // ── Third results route S2b ───────────────────────────────────────────────────────────
  it.each(['matric', 'asasi', 'diploma'])('reads a %s student as the third route, never as SPM', (kind) => {
    const r = resolveCachedResults(store({
      [KEY_EXAM_TYPE]: kind, [KEY_PROFILE]: DEMOGRAPHICS, [KEY_HIGHER_CGPA]: '3.5',
      [KEY_HIGHER_KOKO]: '8', [KEY_MUET_BAND]: '4', [KEY_SPM_PREREQ]: SPM_GRADES,
      [KEY_GRADES]: SPM_GRADES,       // SPM grades on file too: the held route still wins
    }))
    expect(r.view).toBe('higher')
    if (r.view !== 'higher') throw new Error('narrowing')
    expect(r.higher.kind).toBe(kind)
    expect(r.higher.cgpa).toBe(3.5)
    expect(r.higher.spmGrades).toEqual({ bm: 'A', eng: 'B+', math: 'A-' })
    expect(r.profile.grades).toEqual({})
  })

  it('declared third route with no CGPA falls back to the SPM grades held (the Form Six rule)', () => {
    const r = resolveCachedResults(store({
      [KEY_EXAM_TYPE]: 'matric', [KEY_GRADES]: SPM_GRADES, [KEY_PROFILE]: DEMOGRAPHICS,
    }))
    expect(r.view).toBe('spm')
  })

  it('declared third route with nothing at all reads as none, never as an STPM prompt', () => {
    expect(resolveCachedResults(store({ [KEY_EXAM_TYPE]: 'asasi' })).view).toBe('none')
  })
})

describe('the server\'s results_held picks the view when it is known (S2b review)', () => {
  const STORE = {
    [KEY_EXAM_TYPE]: 'spm', [KEY_GRADES]: SPM_GRADES, [KEY_PROFILE]: DEMOGRAPHICS,
    [KEY_HIGHER_CGPA]: '3.5', [KEY_SPM_PREREQ]: SPM_GRADES,
  }
  it('a stale cached "spm" does not hide a held Matriculation result', () => {
    const r = resolveCachedResults(store(STORE), 'matric')
    expect(r.view).toBe('higher')
  })
  it('a stale cached third-route exam does not override a held SPM', () => {
    expect(resolveCachedResults(store({ ...STORE, [KEY_EXAM_TYPE]: 'asasi' }), 'spm').view).toBe('spm')
  })
  it('no served answer: the browser decides, as before', () => {
    expect(resolveCachedResults(store(STORE)).view).toBe('spm')
    expect(resolveCachedResults(store(STORE), '').view).toBe('spm')
  })
})

// Bumi coverage Sprint B: the resolved profile IS the dashboard's results key (react-query keys
// its eligibility check on it, and the STPM check re-runs on it), so the Bumiputera answer must be
// in it — or changing the answer would show the results of the old one.
describe('the Bumiputera answer is part of the results key (Bumi coverage Sprint B)', () => {
  const demo = (extra: Record<string, unknown>) =>
    JSON.stringify({ gender: 'male', nationality: 'malaysian', ...extra })
  const spm = (extra: Record<string, unknown>) => resolveCachedResults(store({
    [KEY_EXAM_TYPE]: 'spm', [KEY_GRADES]: SPM_GRADES, [KEY_PROFILE]: demo(extra),
  }))
  const stpm = (extra: Record<string, unknown>) => resolveCachedResults(store({
    [KEY_EXAM_TYPE]: 'stpm', [KEY_PROFILE]: demo(extra),
    [KEY_STPM_GRADES]: STPM_GRADES, [KEY_STPM_CGPA]: '3.5', [KEY_MUET_BAND]: '4',
  }))
  const bumi = (r: ReturnType<typeof resolveCachedResults>) =>
    r.view === 'spm' || r.view === 'stpm' || r.view === 'higher' ? r.profile.bumiputera : undefined

  it('a Malaysian who said yes carries true, on the SPM and the STPM views', () => {
    expect(bumi(spm({ bumiputera: true }))).toBe(true)
    expect(bumi(stpm({ bumiputera: true }))).toBe(true)
  })

  it('no, unanswered or Foreign carries false', () => {
    expect(bumi(stpm({ bumiputera: false }))).toBe(false)
    expect(bumi(stpm({}))).toBe(false)
    expect(bumi(stpm({ bumiputera: null }))).toBe(false)
    expect(bumi(stpm({ bumiputera: true, nationality: 'non_malaysian' }))).toBe(false)
    expect(bumi(spm({ bumiputera: true, nationality: 'non_malaysian' }))).toBe(false)
  })

  it('changing the answer changes the key', () => {
    const yes = spm({ bumiputera: true })
    const no = spm({ bumiputera: false })
    if (yes.view !== 'spm' || no.view !== 'spm') throw new Error('narrowing')
    expect(JSON.stringify(yes.profile)).not.toEqual(JSON.stringify(no.profile))
  })
})
