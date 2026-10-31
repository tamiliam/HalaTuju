/**
 * The My activity card's words and rules (common profile S5, 2026-10-31; roadmap
 * docs/plans/2026-10-31-common-profile-roadmap.md). The card is `components/adminProfile/ActivityCard`;
 * the rows come from `GET admin/me/activity/` (`apps/scholarship/staff_activity_read.py`).
 *
 * ⚠ THE SERVER DECIDES WHAT MAY BE NAMED; THE WEB DECIDES THE WORDS. A row's subject arrives with a
 * `state`. 'visible' carries a name or a reference (`label`), shown verbatim. 'hidden' and 'removed'
 * carry an ENGLISH neutral word ("a student (removed)") that this card never shows: it says its own,
 * translated, per subject type (`admin.myProfile.activity.subject.<type>.<state>`). The verbs, the
 * subject types and the filters below mirror the server's closed lists in
 * `apps/scholarship/models/staff_activity.py` and `staff_activity_read.FILTERS`, so a verb added
 * there without its words in all three languages turns a test red.
 * drift-test: halatuju-web/src/lib/__tests__/profileActivityDrift.test.ts
 *
 * ⚠ A LINK ONLY WHERE A PAGE EXISTS THAT THIS PERSON MAY OPEN. A visible student opens
 * `/admin/scholarship/<id>` (staff: the cockpit; a source: its own student screen, the same route) —
 * the server marks it visible by the detail view's own rule (D8). A visible payment run opens
 * `/admin/payments/<id>` (visible = `payments_chain.may_read`, the run page's own gate). Every other
 * subject, and anything hidden or removed, is plain text.
 */
import type { ActivityItem, ActivitySubject } from '@/lib/admin-api'
import { formatDateTime } from '@/lib/formatDate'

/** The message namespace of the card. */
export const ACTIVITY_KEY = 'admin.myProfile.activity'

/** Every verb a row can carry — `StaffActivityVerb`'s values, in its order. */
export const ACTIVITY_VERBS = [
  'invitation_sent', 'invitation_accepted', 'first_sign_in', 'profile_updated', 'permissions_changed',
  'assigned', 'unassigned', 'query_raised', 'query_resolved', 'interview_submitted', 'verdict_recorded',
  'verify_accept', 'decline_sent_to_qc', 'declined', 'qc_decision', 'decision_reopened', 'case_closed',
  'contract_witnessed',
  'payment_run_created', 'payment_run_signed', 'tranche_released', 'tranche_withheld', 'tranche_returned',
  'credit_recorded', 'credit_checked', 'credit_confirmed', 'contract_template_created',
  'contract_template_vetted', 'contract_template_submitted', 'contract_template_deployed',
  'contract_countersigned', 'benefactor_vetted', 'invoice_issued', 'invoice_sent', 'invoice_voided',
  'payment_declared', 'payment_confirmed', 'payment_rejected', 'org_request_raised',
  'org_request_approved', 'org_request_declined', 'merchant_flag_opened', 'merchant_flag_closed',
] as const

/** The verbs that are about nobody but the person: their sentence has no `{subject}`. An accepted
 *  invitation's subject is the person's own invitation, so it names nobody else either. */
export const NO_SUBJECT_VERBS: readonly string[] = ['first_sign_in', 'profile_updated', 'invitation_accepted']

/** Every subject type — `StaffActivitySubject`'s values. */
export const ACTIVITY_SUBJECT_TYPES = [
  'application', 'staff', 'invitation', 'payment_run', 'credit', 'contract_template', 'sponsor',
  'invoice', 'org_request', 'merchant_flag',
] as const

/** The subject types whose visible label is a REFERENCE (a run's reference, a template's version,
 *  an invoice's number, a request's number), not a name: shown with their kind in front
 *  (`subject.<type>.named`, "payment run {label}"), so "Prepared {subject}" still reads. */
export const REFERENCE_TYPES: readonly string[] = ['payment_run', 'contract_template', 'invoice', 'org_request']

/** The filters the server accepts (`?kind=`), in the card's order. */
export const ACTIVITY_FILTERS = ['all', 'students', 'money', 'profile'] as const

/** The `meta.role` codes of a payment run signature (`payments_chain.sign`), each with its words. */
const SIGNED_AS = ['maker', 'checker', 'approver']

type T = (k: string, vars?: Record<string, string>) => string

// ── day groups ─────────────────────────────────────────────────────────────────────────────────
export type DayGroup = 'today' | 'week' | 'earlier'

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate())

/** TODAY (the viewer's calendar day), THIS WEEK (since Monday), else EARLIER. A moment ahead of the
 *  viewer's clock (a skewed clock) counts as today, never as "earlier". */
export function dayGroup(iso: string, now: Date): DayGroup {
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return 'earlier'
  const today = startOfDay(now)
  if (at >= today) return 'today'
  const monday = new Date(today)
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7))
  return at >= monday ? 'week' : 'earlier'
}

/** The rows in their groups, newest first, keeping the server's order (it is already newest first). */
export function groupByDay(rows: readonly ActivityItem[], now: Date): { group: DayGroup; rows: ActivityItem[] }[] {
  const out: { group: DayGroup; rows: ActivityItem[] }[] = []
  for (const row of rows) {
    const group = dayGroup(row.created_at, now)
    const last = out[out.length - 1]
    if (last && last.group === group) last.rows.push(row)
    else out.push({ group, rows: [row] })
  }
  return out
}

// ── the sentence ───────────────────────────────────────────────────────────────────────────────
/** A sentence split around `{subject}`: `[before, after]`, or `[whole, null]` when it names none. */
export function sentenceParts(template: string): [string, string | null] {
  const at = template.indexOf('{subject}')
  return at < 0 ? [template, null] : [template.slice(0, at), template.slice(at + '{subject}'.length)]
}

/** The words for the subject: a visible one's own label, verbatim (a reference with its kind in
 *  front); otherwise OUR neutral word, translated — never the server's English one. A visible
 *  subject with no name arrives with `label: null` (TD-445) and takes the neutral word too. */
export function subjectText(subject: ActivitySubject | null, t: T): string {
  if (!subject) return t(`${ACTIVITY_KEY}.something`)
  if (subject.state === 'visible' && subject.label) {
    return REFERENCE_TYPES.includes(subject.type)
      ? t(`${ACTIVITY_KEY}.subject.${subject.type}.named`, { label: subject.label })
      : subject.label
  }
  const removed = subject.state === 'removed'
  const known = (ACTIVITY_SUBJECT_TYPES as readonly string[]).includes(subject.type)
  if (!known) return t(`${ACTIVITY_KEY}.${removed ? 'somethingRemoved' : 'something'}`)
  return t(`${ACTIVITY_KEY}.subject.${subject.type}.${removed ? 'removed' : 'hidden'}`)
}

/** Where a subject opens — only a VISIBLE student or payment run (see the module note). */
export function subjectHref(subject: ActivitySubject | null): string | null {
  if (!subject || subject.state !== 'visible' || !subject.id) return null
  if (subject.type === 'application') return `/admin/scholarship/${subject.id}`
  if (subject.type === 'payment_run') return `/admin/payments/${subject.id}`
  return null
}

/** The grey second line: the time (today) or the date and time, and a short context where the
 *  row's `meta` carries one — today only a payment run signature's part (maker / checker /
 *  approver). Nothing is invented: an unknown code adds nothing. */
export function rowContext(row: ActivityItem, now: Date, t: T): string {
  const at = new Date(row.created_at)
  const when = dayGroup(row.created_at, now) === 'today' && !Number.isNaN(at.getTime())
    ? `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`
    : formatDateTime(row.created_at)
  const role = row.meta?.role
  const parts = [when]
  if (row.verb === 'payment_run_signed' && typeof role === 'string' && SIGNED_AS.includes(role)) {
    parts.push(t(`${ACTIVITY_KEY}.signedAs.${role}`))
  }
  return parts.filter(Boolean).join(' · ')
}
