/**
 * Reviewer detail — the pure decisions behind `/admin/organisation/reviewers[/id]` (#10, 2026-08-02).
 *
 * The server is authoritative on every figure, and on who may read this page at all. This mirrors
 * only what the SCREEN has to decide: how to phrase a measurement we may not have, what the
 * outcome bar is made of, and which credential lines are worth drawing. Nothing here re-derives a
 * rule the server enforces.
 *
 * **The governing constraint, and it is not a style note.** These are thirteen unpaid volunteers.
 * Everything on this page is read by the person who decides who gets the next case, so a figure
 * that invites a ranking has to earn its place. That is why there is no "score", no percentile,
 * and no band that calls anybody slow.
 */
import type { AdminReviewer, AdminReviewerDetail } from './admin-api'

/**
 * How long a student waits, banded — and **only the actionable end is banded**.
 *
 * `unknown` is its own answer, never folded into 0: six of the thirteen have completed nothing
 * yet, and "no measurement" must not render as "instant". `waiting` fires at 14 days, which is
 * about the student's wait, not the reviewer's speed — a case older than a fortnight is one
 * somebody should ask about, whoever holds it.
 *
 * Nothing on production reaches it today (the slowest median is 10.3 days). A guard that does not
 * fire on current data is doing its job, not missing.
 */
export type TurnaroundBand = 'unknown' | 'measured' | 'waiting'

export const LONG_WAIT_DAYS = 14

export function turnaroundBand(days: number | null): TurnaroundBand {
  if (days === null) return 'unknown'
  return days >= LONG_WAIT_DAYS ? 'waiting' : 'measured'
}

/**
 * Whether this reviewer is holding anything at all — the difference between "free" and "idle".
 *
 * Deliberately not a band with a colour. An empty caseload is the normal state of a volunteer
 * between assignments and must not read as a criticism.
 */
export function isFree(r: AdminReviewer): boolean {
  return r.open_now === 0
}

/**
 * What became of the cases this reviewer decided, as bar segments.
 *
 * `decided_by_other` is deliberately **not** a segment: those are cases assigned to them that
 * somebody else ruled on, so they are not this person's outcomes at all. The page states that
 * number separately, in words, because silently dropping it would make the bar disagree with the
 * caseload beside it.
 */
export type OutcomeKey = 'recommended' | 'declined' | 'rejectedAfterReview' | 'awaitingQc'

export interface OutcomeSegment {
  key: OutcomeKey
  count: number
  /** Percentage of DECIDED cases, rounded — for the bar's width only, never displayed alone. */
  pct: number
}

/**
 * The four bands, in the order a case travels.
 *
 * ⚠ **`declined` AND `rejectedAfterReview` ARE NOT ONE BAND.** A reviewer who recommended a student
 * who was then rejected by QC, an org_admin or a super declined nobody, and a screen that colours
 * the two alike accuses them of a decision they did not make. Owner's ruling, 2026-08-02.
 *
 * ⚠ **`awaitingQc` exists so the bar RECONCILES with the Completed figure above it.** Without it
 * production showed Yuvarajan at Completed 6 over a bar totalling 5 — two of his decided cases were
 * sitting with QC and appeared nowhere. The server guarantees the four partition the decided cases.
 *
 * Zero-count bands are kept, not filtered: the legend states all four every time, so the reader
 * learns the vocabulary instead of wondering why a colour vanished.
 */
export function outcomeSegments(d: AdminReviewerDetail): OutcomeSegment[] {
  const counts: Array<[OutcomeKey, number]> = [
    ['recommended', d.recommended],
    ['declined', d.declined],
    ['rejectedAfterReview', d.rejected_after_review],
    ['awaitingQc', d.awaiting_qc],
  ]
  const total = counts.reduce((n, [, c]) => n + c, 0)
  if (total === 0) return []
  return counts.map(([key, count]) => ({
    key, count, pct: Math.round((count / total) * 100),
  }))
}

/** True when there is nothing to draw a history from — the page shows an honest empty state. */
export function hasNoHistory(d: AdminReviewerDetail): boolean {
  return d.completed === 0 && d.open_now === 0
}

/**
 * A reviewer's phone as it should be READ, with its country code.
 *
 * ⚠ The number is STORED without one. `/admin/profile` renders `+60` as fixed chrome beside the
 * input and saves only the local part, so all fourteen reviewers' rows read like `12-624 5544`.
 * Prefixing here is display-only and deliberate — rewriting the stored values would break the
 * editor's contract with every reviewer who has already filled it in.
 *
 * An already-international number is left exactly as typed: somebody who entered `+65…` meant it.
 */
export function displayPhone(phone: string): string {
  const value = (phone || '').trim()
  if (!value) return ''
  if (value.startsWith('+')) return value
  // A leading 0 is the domestic form of the same number; +60 replaces it.
  return `+60 ${value.replace(/^0/, '')}`
}

/**
 * The credential lines, blanks dropped.
 *
 * `ReviewerProfile` is filled in by the reviewer themselves and most fields are optional, so
 * rendering the labels unconditionally would draw a form of empty rows — which reads as data we
 * lost rather than data they never gave. An absent profile yields an empty list, not a crash.
 */
export interface CredentialLine {
  key: 'qualification' | 'university' | 'graduationYear' | 'fieldOfStudy'
  value: string
}

export function credentialLines(d: AdminReviewerDetail): CredentialLine[] {
  const out: CredentialLine[] = []
  if (d.qualification) out.push({ key: 'qualification', value: d.qualification })
  if (d.university) out.push({ key: 'university', value: d.university })
  if (d.graduation_year) out.push({ key: 'graduationYear', value: String(d.graduation_year) })
  if (d.field_of_study) out.push({ key: 'fieldOfStudy', value: d.field_of_study })
  return out
}

/** The languages a reviewer can interview in, in a fixed order so the chips never re-shuffle. */
const LANG_ORDER = ['en', 'ms', 'ta']

export function orderedLanguages(r: AdminReviewer): string[] {
  return LANG_ORDER.filter((code) => r.languages.includes(code))
}

/**
 * How to phrase the phone.
 *
 * Three states, not two. `none` means they never gave one; `staff_only` means they gave it and
 * withheld consent to pass it to students — an admin may still ring them, and the screen must say
 * which, because quietly showing a number a reviewer marked private would defeat the consent this
 * organisation asked them for.
 */
export type PhoneState = 'none' | 'staff_only' | 'shared'

export function phoneState(d: AdminReviewerDetail): PhoneState {
  if (!d.phone) return 'none'
  return d.share_phone_with_students ? 'shared' : 'staff_only'
}
