/**
 * Single source of truth for a ScholarshipApplication's status VOCABULARY on the
 * officer-facing admin surface: one label (via i18n key) and one tone per status.
 *
 * Before this module the status was described in four drifting places and coloured in two
 * contradictory ones (see docs/plans/2026-07-14-status-vocabulary-and-stage-colours.md). Every
 * admin screen now imports from here, and applicationStatus.test.ts fails if a screen invents
 * its own status→label or status→colour map again.
 *
 * Pure module — no React, no i18n import. It returns i18n KEYS; the caller does `t(...)`. This
 * mirrors how officerCockpit.ts is built and keeps it jest-testable in the node env.
 *
 * Colour is SEMANTIC with a depth ramp: the label already carries the stage's identity, so hue
 * carries its MEANING — blue = in progress (deepening down the funnel), green = committed
 * (deepening down the funnel), grey = ended, red = rejected. Amber is RESERVED for "needs
 * attention" (`reopened`), matching what amber means everywhere else in the product, and is no
 * longer spent on ordinary in-progress stages.
 */

/** The 13 real DB statuses in funnel order. Mirrors `STATUS_CHOICES` in
 *  halatuju_api/apps/scholarship/models.py. Also drives the list's filter dropdown, which used to
 *  silently omit `withdrawn` and `expired`. */
export const APPLICATION_STATUSES = [
  'submitted',
  'shortlisted',
  'profile_complete',
  'interviewing',
  'interviewed',
  'recommended',
  'awarded',
  'active',
  'maintenance',
  'closed',
  'withdrawn',
  'expired',
  'rejected',
] as const

/** Synthetic statuses — rendered from application state, not stored as a DB value.
 *  `reopened` is shown when `decision_reopened_at` is set (see `displayStatus`). */
export const SYNTHETIC_STATUSES = ['reopened'] as const

/** Tailwind tone per status. Tones MUST be complete literal class names — Tailwind's JIT scanner
 *  cannot see a class assembled at runtime, so `` `bg-blue-${n}` `` would silently ship unstyled. */
const STATUS_TONE: Record<string, string> = {
  // In progress — a deepening blue ramp down the funnel.
  submitted: 'bg-info-50 text-info-700',
  shortlisted: 'bg-info-100 text-info-700',
  profile_complete: 'bg-info-200 text-info-800',
  interviewing: 'bg-info-300 text-info-900',
  interviewed: 'bg-info-fill text-info-fill-ink',
  // Committed — a deepening green ramp down the funnel.
  recommended: 'bg-positive-100 text-positive-800',
  awarded: 'bg-positive-200 text-positive-900',
  active: 'bg-positive-300 text-positive-900',
  maintenance: 'bg-positive-400 text-positive-900',
  // Ended — grey.
  closed: 'bg-ground-100 text-ground-600',
  withdrawn: 'bg-ground-100 text-ground-600',
  expired: 'bg-ground-100 text-ground-600',
  // Rejected — red.
  rejected: 'bg-critical-100 text-critical-700',
  // Needs attention — amber (reserved).
  reopened: 'bg-caution-100 text-caution-700',
}

const DEFAULT_TONE = 'bg-ground-100 text-ground-600'

/** i18n key for a status label. Wrapping the prefix here means callers can't misspell it.
 *  (officerCockpit.headerTimeline already emits bare `labelKey` suffixes — those stay as they are.) */
export function statusLabelKey(status: string): string {
  return `admin.scholarship.statuses.${status}`
}

/** Tailwind tone classes for a status, with a safe grey default for an unknown status. */
export function statusTone(status: string): string {
  return STATUS_TONE[status] || DEFAULT_TONE
}

/** Whether a status has an EXPLICIT tone (vs falling through to the grey default). The ended
 *  states are legitimately grey too, so this membership check — not "differs from grey" — is how
 *  the guardrail catches a new status added to the enum without a colour. */
export function hasStatusTone(status: string): boolean {
  return Object.prototype.hasOwnProperty.call(STATUS_TONE, status)
}

/** The status to DISPLAY for an application: a super-reopened decision shows "Reopened",
 *  overriding the stored accepted/rejected. Previously duplicated in both admin pages. */
export function displayStatus(app: { status: string; decision_reopened_at?: string | null }): string {
  return app.decision_reopened_at ? 'reopened' : app.status
}
