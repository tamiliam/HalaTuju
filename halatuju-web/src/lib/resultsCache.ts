/**
 * What results does THIS BROWSER hold, and what should the dashboard draw from them?
 *
 * ⚠ THE CACHE IS NOT THE RECORD. The dashboard reads results out of localStorage (they arrive
 * there from the server via AuthProvider's caching effect), and for a long time it treated "not in
 * the cache" as "this student has no profile" — the screen said *No profile found. Please complete
 * the onboarding.* to somebody who had completed it. Two ways that happened, and both are fixed by
 * the callers reading this module rather than deciding for themselves:
 *
 *   1. **Nothing cached YET.** The page read the cache once on mount, which is before the profile
 *      has been fetched. The caller must re-read once the profile lands (pass it in the effect's
 *      dependencies), or the first view after any sign-in is the empty state.
 *
 *   2. **An STPM student who has not sat STPM.** `exam_type` answers two different questions in
 *      this codebase — "which exam's results do I hold?" (onboarding, this module) and "which
 *      pathway am I entering?" (the bursary application). For somebody entering Form 6 those
 *      genuinely disagree: they hold SPM results and are heading INTO STPM. Their profile reads
 *      `exam_type='stpm'` with no STPM grades, no CGPA and no MUET band, so the STPM branch could
 *      never assemble anything — while the onboarding guard, which reads the SERVER, saw their SPM
 *      grades and correctly refused to send them back to onboarding. Server says onboarded, cache
 *      says nothing, and the page believed the cache. Reported as org request #11, 2026-08-13;
 *      2 of 35 STPM profiles were in that state.
 *
 * ⚠ **AN INCOMPLETE STPM SET FALLS BACK TO SPM WHEN SPM RESULTS ARE THERE** — it does not read as
 * "no results". Those SPM grades are real, they are what a Form 6 entrant browses courses on, and
 * showing them is strictly better than a dead end. `stpm_pending` is reserved for the case where
 * there is genuinely nothing to fall back to, and it asks for the missing STPM results rather than
 * for onboarding the student has already done.
 */
import type { StudentProfile } from '@/lib/api'
import {
  KEY_ALIRAN, KEY_EXAM_TYPE, KEY_GRADES, KEY_MERIT, KEY_MUET_BAND, KEY_PROFILE,
  KEY_SPM_PREREQ, KEY_STPM_CGPA, KEY_STPM_GRADES,
} from '@/lib/storage'

/** Just the read half of `localStorage`, so this stays testable without a DOM. */
export interface ReadableStore {
  getItem(key: string): string | null
}

export interface StpmCache {
  stpmGrades: Record<string, string>
  cgpa: number
  muetBand: number
  spmGrades: Record<string, string>
}

export type CachedResults =
  | { view: 'stpm'; profile: StudentProfile; stpm: StpmCache }
  | { view: 'spm'; profile: StudentProfile }
  /** Declared STPM, results not entered yet, and no SPM grades to fall back to. */
  | { view: 'stpm_pending' }
  /** This browser holds nothing. Before hydration this is expected — re-read, do not conclude. */
  | { view: 'none' }

function parse<T>(raw: string | null): T | null {
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null            // malformed — treat as absent, never throw into a render
  }
}

function demographics(store: ReadableStore): Record<string, unknown> {
  return parse<Record<string, unknown>>(store.getItem(KEY_PROFILE)) ?? {}
}

function spmProfile(store: ReadableStore): StudentProfile | null {
  const grades = parse<Record<string, string>>(store.getItem(KEY_GRADES))
  const raw = store.getItem(KEY_PROFILE)
  if (!grades || Object.keys(grades).length === 0 || !raw) return null
  const d = demographics(store)
  const merit = store.getItem(KEY_MERIT)
  const stream = parse<string[]>(store.getItem(KEY_ALIRAN))
  return {
    grades,
    gender: d.gender as StudentProfile['gender'],
    nationality: d.nationality as StudentProfile['nationality'],
    colorblind: !!d.colorblind,
    disability: !!d.disability,
    coq_score: (d.coqScore as number) ?? 5.0,
    ...(stream && stream.length ? { stream_subjects: stream } : {}),
    ...(merit ? { student_merit: parseFloat(merit) } : {}),
  } as StudentProfile
}

function stpmCache(store: ReadableStore): StpmCache | null {
  const grades = parse<Record<string, string>>(store.getItem(KEY_STPM_GRADES))
  const cgpa = store.getItem(KEY_STPM_CGPA)
  const muet = store.getItem(KEY_MUET_BAND)
  // All three, deliberately: a partial set cannot be scored, and half an answer on a results page
  // is worse than saying the results are not in yet.
  if (!grades || Object.keys(grades).length === 0 || !cgpa || !muet) return null
  return {
    stpmGrades: grades,
    cgpa: parseFloat(cgpa),
    muetBand: parseInt(muet),
    spmGrades: parse<Record<string, string>>(store.getItem(KEY_SPM_PREREQ)) ?? {},
  }
}

/** Resolve what the dashboard should draw. See the module docstring before changing the order. */
export function resolveCachedResults(store: ReadableStore): CachedResults {
  const examType = store.getItem(KEY_EXAM_TYPE) || 'spm'

  if (examType === 'stpm') {
    const stpm = stpmCache(store)
    if (stpm) {
      const d = demographics(store)
      return {
        view: 'stpm',
        stpm,
        profile: {
          grades: {},
          gender: (d.gender as StudentProfile['gender']) || 'male',
          nationality: (d.nationality as StudentProfile['nationality']) || 'malaysian',
          colorblind: !!d.colorblind,
          disability: !!d.disability,
        } as StudentProfile,
      }
    }
    // Declared STPM, no STPM results. The SPM grades they DO hold are the better answer.
    const spm = spmProfile(store)
    return spm ? { view: 'spm', profile: spm } : { view: 'stpm_pending' }
  }

  const spm = spmProfile(store)
  return spm ? { view: 'spm', profile: spm } : { view: 'none' }
}
