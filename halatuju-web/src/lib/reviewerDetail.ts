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
export interface OutcomeSegment {
  key: 'progressed' | 'declined'
  count: number
  /** Percentage of DECIDED cases, rounded — for the bar's width only, never displayed alone. */
  pct: number
}

export function outcomeSegments(d: AdminReviewerDetail): OutcomeSegment[] {
  const total = d.progressed + d.declined
  if (total === 0) return []
  const pct = (n: number) => Math.round((n / total) * 100)
  return [
    { key: 'progressed', count: d.progressed, pct: pct(d.progressed) },
    { key: 'declined', count: d.declined, pct: pct(d.declined) },
  ]
}

/** True when there is nothing to draw a history from — the page shows an honest empty state. */
export function hasNoHistory(d: AdminReviewerDetail): boolean {
  return d.completed === 0 && d.open_now === 0 && d.decided_by_other === 0
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
