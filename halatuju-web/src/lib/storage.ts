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

/** TD-342: a pending action is stamped (`at`) when written and is stale after this long — a Google
 *  sign-in abandoned and finished later must not send her back to an old gift. No `at` = older write = fresh. */
export const PENDING_AUTH_TTL_MS = 30 * 60 * 1000
export function isStalePendingAction(p: { at?: unknown } | null | undefined, now = Date.now()): boolean {
  return typeof p?.at === 'number' && now - p.at > PENDING_AUTH_TTL_MS
}

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

/** Remove this student's halatuju_* keys from localStorage AND this tab's sessionStorage. */
/** Auth scopes that share the `halatuju_` prefix but belong to OTHER user types —
 *  a student logout must NOT wipe the admin / sponsor sessions (they're isolated
 *  Supabase clients with their own storage keys, incl. their PKCE verifiers). */
const PRESERVE_ON_CLEAR = ['halatuju_admin_session', 'halatuju_sponsor_session']

export function clearAll(): void {
  Object.keys(localStorage)
    .filter(k => k.startsWith('halatuju_') && !PRESERVE_ON_CLEAR.some(p => k.startsWith(p)))
    .forEach(k => localStorage.removeItem(k))
  // ⚠ AND THIS TAB'S sessionStorage. The apply form stashes the WHOLE form there (IC, income,
  // parent name and phone, the typed signature — `APPLY_STASH_KEY`) for the "edit my results"
  // round trip, and sign-out reloads the SAME tab, so it survived: the next student to sign in on a
  // shared phone opened /scholarship/apply pre-filled with the last student's details (found by
  // Mobile M4's audit). The admin and sponsor flows keep their own tab state.
  clearStudentTab()
}

/** Only the tab half of `clearAll`: a session that ends WITHOUT the sign-out button (revoked,
 *  a failed refresh, a sign-out in another tab) runs this from the auth listener. Not `clearAll`:
 *  a signed-out visitor's grades live only in localStorage, and a refresh failure must not wipe them. */
export function clearStudentTab(): void {
  try {
    Object.keys(sessionStorage)
      .filter(k => k.startsWith('halatuju_') && !SESSION_PRESERVE.some(p => k.startsWith(p)))
      .forEach(k => sessionStorage.removeItem(k))
  } catch { /* sessionStorage unavailable — nothing is held there */ }
}

/** TD-458: the user id whose student data this browser's `halatuju_` keys hold (`claimStudentData`). */
export const KEY_OWNER = 'halatuju_owner'

/**
 * TD-458 (shared phone): bind this browser's student data to the signed-in account. Called with the
 * user id of every real session the student auth stack sees, and with null for an anonymous session
 * or a SIGNED_OUT. Data tagged to ANOTHER owner is that owner's (hydrated from, or synced into, their
 * account, so the server holds it): it is wiped as the sign-out button would (`clearAll`, keeping
 * only the language) before the sign-in sync could upload it into the next account. Untagged data
 * is a signed-out visitor's own and is left alone, as before. Returns true when it wiped, so the
 * caller can rebuild any screen that already copied the wiped data into memory.
 */
export function claimStudentData(userId: string | null): boolean {
  try {
    const owner = localStorage.getItem(KEY_OWNER)
    const wipe = !!owner && owner !== userId
    if (wipe) {
      const locale = localStorage.getItem(KEY_LOCALE)
      clearAll()
      if (locale) localStorage.setItem(KEY_LOCALE, locale)
    }
    if (userId) localStorage.setItem(KEY_OWNER, userId)
    return wipe
  } catch { return false /* storage unavailable: nothing is held */ }
}

/** Tab state that belongs to the OTHER user types (an admin's list navigation, a sponsor's
 *  half-finished registration) — a student's sign-out must not wipe it. */
const SESSION_PRESERVE = ['halatuju_admin_', 'halatuju_list_nav:scholarship', 'halatuju_sponsor_']

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
  // The header on screen re-reads the hint at once (S3 review L5), not at the next navigation.
  try { window.dispatchEvent(new Event(BURSARY_FILE_EVENT)) } catch { /* no window (server) */ }
}

/** Fired by `rememberBursaryFile`; the header listens for it. */
export const BURSARY_FILE_EVENT = 'halatuju:bursary-file'

/** Whether the header should offer "My Bursary" (see `KEY_HAS_BURSARY_FILE`). */
export function hasBursaryFile(): boolean {
  try { return localStorage.getItem(KEY_HAS_BURSARY_FILE) === '1' } catch { return false }
}
