/**
 * Centralised localStorage key constants and typed helpers.
 *
 * All halatuju_* localStorage access should go through these constants.
 * Single source of truth — prevents key mismatch bugs across pages.
 */

// ── Key constants ────────────────────────────────────────────────────

/** SPM grades object: Record<string, string> e.g. {"bm":"A","eng":"B+"} */
export const KEY_GRADES = 'halatuju_grades'

/** Student profile demographics: {gender, nationality, colorblind, disability, ...} */
export const KEY_PROFILE = 'halatuju_profile'

/** Selected stream: 'sains' | 'sastera' | 'teknikal' | 'vokasional' */
export const KEY_STREAM = 'halatuju_stream'

/** Selected aliran within stream */
export const KEY_ALIRAN = 'halatuju_aliran'

/** Selected elective subjects JSON array */
export const KEY_ELEKTIF = 'halatuju_elektif'

/** Computed SPM merit score (number as string) */
export const KEY_MERIT = 'halatuju_merit'

/** Quiz signals object: {work_preference_signals, environment_signals, ...} */
export const KEY_QUIZ_SIGNALS = 'halatuju_quiz_signals'

/** Quiz signal strength: {hands_on: "strong", ...} */
export const KEY_SIGNAL_STRENGTH = 'halatuju_signal_strength'

/** Whether a report has been generated: 'true' | absent */
export const KEY_REPORT_GENERATED = 'halatuju_report_generated'

/** Exam type: 'spm' | 'stpm' | 'matric' | 'asasi' | 'diploma' (the last three: the third results route) */
export const KEY_EXAM_TYPE = 'halatuju_exam_type'
/**
 * Which exam's results were last COMPLETED — distinct from KEY_EXAM_TYPE, which is set by
 * merely SELECTING an exam and needs no results behind it. Written by the two results
 * editors when their form is finished, and synced to `profile.results_exam_type`.
 */
export const KEY_RESULTS_EXAM_TYPE = 'halatuju_results_exam_type'

/** Third results route (S2b): the Matriculation / Asasi / Diploma CGPA AS PRINTED (number as string).
 *  Which of the three is KEY_EXAM_TYPE / KEY_RESULTS_EXAM_TYPE. The overall CGPA is never stored
 *  here — the server computes it (`exam_questions.overall_cgpa`). */
export const KEY_HIGHER_CGPA = 'halatuju_higher_cgpa'

/** Third results route: the Matriculation / Asasi co-curriculum score, 0-10 (absent for Diploma). */
export const KEY_HIGHER_KOKO = 'halatuju_higher_koko'

/** Third results route, Diploma only: 'public' (only a public diploma counts, ruling D5). */
export const KEY_HIGHER_INSTITUTION = 'halatuju_higher_institution'

/** STPM grades object: Record<string, string> */
export const KEY_STPM_GRADES = 'halatuju_stpm_grades'

/** STPM overall CGPA (number as string) */
export const KEY_STPM_CGPA = 'halatuju_stpm_cgpa'

/** MUET band (number as string) */
export const KEY_MUET_BAND = 'halatuju_muet_band'

/** SPM prerequisite grades for STPM pathway */
export const KEY_SPM_PREREQ = 'halatuju_spm_prereq'

/** STPM stream: 'science' | 'arts' */
export const KEY_STPM_STREAM = 'halatuju_stpm_stream'

/** Koko score for STPM (string) */
export const KEY_KOKO_SCORE = 'halatuju_koko_score'

/** STPM CGPA C4: '1' = the STPM step's Continue just saved a co-curriculum score (the student's own
 *  confirmation). The next profile sync sends `stpm_koko_confirmed` and removes it; a sign-in resend
 *  of the stored score never carries it. */
export const KEY_STPM_KOKO_CONFIRMED = 'halatuju_stpm_koko_confirmed'

/** SPM stream for STPM prereq entry: 'science' | 'arts' | 'technical' | 'vocational' */
export const KEY_SPM_STREAM = 'halatuju_spm_stream'

/** STPM path: the SPM stream (aliran) subjects picked as prerequisites — JSON array. Not
 *  stored on the server: after a login the form derives it from the prerequisite grades (TD-069). */
export const KEY_SPM_ALIRAN = 'halatuju_spm_aliran'

/** STPM path: the SPM elective subjects picked as prerequisites — JSON array, up to
 *  MAX_SPM_ELECTIVES. Synced to `profile.spm_elective_subjects` (TD-069). */
export const KEY_SPM_ELEKTIF = 'halatuju_spm_elektif'

/** UI locale: 'en' | 'ms' | 'ta' */
export const KEY_LOCALE = 'halatuju_locale'

/** Pending auth action (pre-login intent) */
export const KEY_PENDING_AUTH_ACTION = 'halatuju_pending_auth_action'

/** Resume action after login (save course, generate report, etc.) */
export const KEY_RESUME_ACTION = 'halatuju_resume_action'

/** Referral source: partner code or self-reported channel */
export const KEY_REFERRAL_SOURCE = 'halatuju_referral_source'

/** STPM quiz signals: {riasec_seed: {...}, field_interest: {...}, ...} */
export const KEY_STPM_QUIZ_SIGNALS = 'halatuju_stpm_quiz_signals'

/** STPM quiz branch: 'science' | 'arts' | 'mixed' */
export const KEY_STPM_QUIZ_BRANCH = 'halatuju_stpm_quiz_branch'

/** Sponsor registration details stashed before email/password sign-up, so the
 *  portal's "complete your details" step can pre-fill them after the user
 *  confirms their email (when no session is returned at sign-up time). */
export const KEY_SPONSOR_PENDING = 'halatuju_sponsor_pending'

/** F4 — the referral code from a /sponsor?ref=<code> invite link. Captured on
 *  arrival and read at register time so attribution survives the sign-in round-trip. */
export const KEY_SPONSOR_REF = 'halatuju_sponsor_ref'

// ── Display constants ────────────────────────────────────────────────

/** Student maintenance S3: '1' when the signed-in student has a "My Bursary" file. A DISPLAY HINT
 *  for the header's link only — written by the pages that already read her applications
 *  (`rememberBursaryFile`), wiped with every other `halatuju_` key at sign-out. Never a gate: the
 *  hub's own endpoint answers 404 for a student with no file. */
export const KEY_HAS_BURSARY_FILE = 'halatuju_has_bursary_file'

/** Number of course cards shown initially (anon and logged-in). Anon users hit auth gate on "Load More". */
export const COURSE_PAGE_SIZE = 9

// ── Helpers ──────────────────────────────────────────────────────────

/** Remove all halatuju_* keys from localStorage. */
/** Auth scopes that share the `halatuju_` prefix but belong to OTHER user types —
 *  a student logout must NOT wipe the admin / sponsor sessions (they're isolated
 *  Supabase clients with their own storage keys, incl. their PKCE verifiers). */
const PRESERVE_ON_CLEAR = ['halatuju_admin_session', 'halatuju_sponsor_session']

export function clearAll(): void {
  Object.keys(localStorage)
    .filter(k => k.startsWith('halatuju_') && !PRESERVE_ON_CLEAR.some(p => k.startsWith(p)))
    .forEach(k => localStorage.removeItem(k))
}

/** Check if the user has entered any results (SPM or STPM grades, or a third-route CGPA). */
export function hasGrades(): boolean {
  try {
    if (localStorage.getItem(KEY_HIGHER_CGPA)) return true
    const spm = localStorage.getItem(KEY_GRADES)
    if (spm && Object.keys(JSON.parse(spm)).length > 0) return true
    const stpm = localStorage.getItem(KEY_STPM_GRADES)
    if (stpm && Object.keys(JSON.parse(stpm)).length > 0) return true
  } catch {
    // Malformed JSON — treat as no grades
  }
  return false
}

/** Record whether the student has a bursary file (the header's "My Bursary" link reads it). */
export function rememberBursaryFile(has: boolean): void {
  try {
    if (has) localStorage.setItem(KEY_HAS_BURSARY_FILE, '1')
    else localStorage.removeItem(KEY_HAS_BURSARY_FILE)
  } catch { /* storage unavailable — the link simply does not show */ }
}

/** Whether the header should offer "My Bursary" (see `KEY_HAS_BURSARY_FILE`). */
export function hasBursaryFile(): boolean {
  try { return localStorage.getItem(KEY_HAS_BURSARY_FILE) === '1' } catch { return false }
}
