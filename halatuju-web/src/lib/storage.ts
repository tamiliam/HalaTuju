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

/** Exam type: 'spm' | 'stpm' */
export const KEY_EXAM_TYPE = 'halatuju_exam_type'

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

/** UI locale: 'en' | 'ms' | 'ta' */
export const KEY_LOCALE = 'halatuju_locale'

/** Pending auth action (pre-login intent) */
export const KEY_PENDING_AUTH_ACTION = 'halatuju_pending_auth_action'

/** Resume action after login (save course, generate report, etc.) */
export const KEY_RESUME_ACTION = 'halatuju_resume_action'

/** Referral source: partner code or self-reported channel */
export const KEY_REFERRAL_SOURCE = 'halatuju_referral_source'

// ── Helpers ──────────────────────────────────────────────────────────

/** Remove all halatuju_* keys from localStorage. */
export function clearAll(): void {
  Object.keys(localStorage)
    .filter(k => k.startsWith('halatuju_'))
    .forEach(k => localStorage.removeItem(k))
}
