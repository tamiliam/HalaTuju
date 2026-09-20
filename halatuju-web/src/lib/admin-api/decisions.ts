/**
 * The decisions that are irreversible or nearly so: rejecting, the org-admin reject, the
 * decline, holding a pending award, verifying an acceptance, and the reporting date.
 *
 * ⚠ `orgRejectApplication` is gated in the api to super/org_admin ONLY.
 * The cockpit's matching gate is `canOrgReject` in `@/lib/officerCockpit`.
 */
import { adminMutate } from './client'
import type { ApiOptions } from './client'
import type { AdminScholarshipDetail } from './applications'

/** Post-shortlist admin rejection. category: 'interview' (reviewed, not selected — from
 * shortlisted onward) or 'contractual' (failed post-award steps — from accepted). Sends the
 * bucket's decline email. */
export async function rejectApplication(
  id: number, category: 'interview' | 'contractual', options?: ApiOptions
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/reject/`, 'POST', { category }, options
  )
}

/** Org-admin reject of a stuck SHORTLISTED applicant (bucket 'incomplete'). super/org_admin ONLY
 * — a qc or the assigned reviewer is refused 403 (unlike `rejectApplication`). IMMEDIATE and
 * IRREVERSIBLE: no cool-off, the decline email goes at once and there is no cancel window.
 * `comments` is required (400 comments_required) and stays internal — the student gets the
 * generic warm decline, never this text. */
export async function orgRejectApplication(
  id: number, comments: string, options?: ApiOptions
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/org-reject/`, 'POST', { comments }, options
  )
}

/** Org-admin manual re-send of the "you haven't submitted yet" reminder to a shortlisted,
 * consented-but-unsubmitted student (the manual counterpart to the one-time auto nudge). */
export async function nudgeStudent(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/nudge/`, 'POST', {}, options
  )
}

/** Record the date a student reports to their institution, when the offer letter carries no
 * readable one. Not cosmetic: it sizes the bursary (a course begun before the cohort year = a
 * continuing student), gates payment eligibility, and triggers the semester-result request —
 * which is why QC refuses to accept a case without it. super / org_admin / qc / assigned
 * reviewer. `date` is ISO 'YYYY-MM-DD'. */
export async function setReportingDate(id: number, date: string, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/reporting-date/`, 'POST', { date }, options
  )
}

/** Cancel a scheduled-but-unrevealed decline within the cool-off (the student never saw it). */
export async function cancelPendingDecline(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/cancel-decline/`, 'POST', {}, options
  )
}

/** Hold an accepted-but-unconfirmed award within the cool-off (amount returns to the sponsor). */
export async function holdPendingAward(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/hold-award/`, 'POST', {}, options
  )
}

/** Verify the checklist + accept: sets nric_verified (locks NRIC), advances → accepted. */
export async function verifyAcceptApplication(
  id: number, checklist: Record<string, boolean>, options?: ApiOptions
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/verify-accept/`, 'POST', { checklist }, options
  )
}

/** Reviewer sends a DECLINE verdict to QC (→ AWAITING QC), instead of rejecting directly. QC then
 * confirms the decline (→ rejected) or reopens it. Requires a recorded decline verdict. */
export async function submitDeclineApplication(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/submit-decline/`, 'POST', {}, options
  )
}

/** Toggle the coordinator-facing mentoring-candidate flag. */
export async function setMentoringCandidate(id: number, value: boolean, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/`, 'PATCH', { mentoring_candidate: value }, options
  )
}

