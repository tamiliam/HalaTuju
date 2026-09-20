/**
 * The bursary application as the cockpit sees it: the list row, the whole detail payload,
 * assignment, asking for more information, and who may be assigned.
 *
 * ⚠ `AdminScholarshipDetail` is the widest type in the app and is read by the whole cockpit.
 * It is NOT split further: every field on it comes from one serializer, and a type whose
 * halves live in two files is a type nobody can read in one go.
 *
 * ⚠ FOUR SPANS of the old `admin-api.ts` (863-1191, 1315-1371, 1398-1425, 1462-1465).
 */
import type { BursaryAgreement } from '@/lib/api'
import type { IncomeShownMap } from '@/lib/incomeShown'

import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import { DEFAULT_ADMIN_PAGE_SIZE } from './partners'
import type { InterviewSchedule } from './interviews'
import type {
  AdminAgendaEntry, AdminAnomaly, AdminFundingEstimate, AdminQuerySla, AdminSubmissionReview,
  AdminVerdictFact,
} from './verdict'
import type { AdminApplicantDocument, AdminReferee } from './documents'
import type { AdminResolutionItem } from './resolution'
import type { AdminDisbursement, MaintenanceSubstate } from './lifecycle'

// ── Scholarship (BrightPath Bursary Programme) ──────────────────────────────

export interface AdminScholarshipListItem {
  id: number
  name: string
  profile_id: string | null
  cohort_code: string
  qualification: string
  spm_a_count: number | null
  stpm_pngk: number | null
  referral_source: string | null   // the referring org chosen at apply (Source column)
  merit_score: number | null       // course-guide merit (SPM 0-100 / STPM PNGK), computed live
  call_language: string            // student's preferred call language: en/ms/ta/mixed/'' — for reviewer matching
  status: string
  bucket: string
  shortlist_reason: string
  submitted_at: string
  profile_completed_at: string | null
  assigned_to_id: number | null
  assigned_to_name: string | null
  // Server-computed: may this case change hands at all right now (Completed / interviewing only)?
  // The dropdown is disabled when false — the server refuses anyway, and an action that will be
  // refused should not look available.
  assignable: boolean
  // Server-computed first-assign readiness (services.is_ready_for_assignment): all student tasks
  // done OR the 5-day window lapsed. The dropdown disables a FIRST assignment while false, so the
  // list cannot offer an assign the server refuses.
  // NOT a copied rule: this is the SERVED answer, and the detail cockpit reads the same field on
  // its own payload (`firstAssignBlocked = !assigned_to_id && !ready_for_assignment`). Neither
  // screen re-derives readiness, which is why there is nothing here for a drift test to hold.
  ready_for_assignment: boolean
  decision_reopened_at: string | null   // when set, the pill shows "Reopened" (overrides accepted/rejected)
}

export interface AdminCompleteness {
  quiz_done: boolean
  details_done: boolean
  funding_done: boolean
  documents_done: boolean
  consent_done: boolean
  address_done: boolean
  guardian_docs_done: boolean
  family_done: boolean
  complete: boolean
}

export interface AdminInterviewSession {
  id: number
  status: 'draft' | 'submitted'
  findings: Record<string, { verdict: string; rationale: string }>
  rubric: Record<string, number>
  overall_note: string
  interviewer_name: string | null
  started_at: string | null
  submitted_at: string | null
  updated_at: string
}

export interface AdminSponsorProfile {
  draft_markdown: string
  edited_markdown: string
  current_markdown: string
  status: string
  model_used: string
  generated_at: string | null
  published_at: string | null
  updated_at: string
  // Phase D — the "v2" profile refined with interview findings (admin-facing for now).
  final_markdown: string
  final_model_used: string
  finalised_at: string | null
  // Phase E2 — the ANONYMOUS, sponsor-pool-facing profile (generate -> publish).
  anon_markdown: string
  anon_model_used: string
  anon_generated_at: string | null
  anon_published: boolean
  anon_published_at: string | null
}

/** The "you haven't submitted yet" nudge state (server-computed). `applicable` = the student is
 *  shortlisted + consented + unsubmitted; `available` = a manual reminder may be sent right now;
 *  `available_at` = when it next becomes available (auto-due time, or cooldown end). */
export interface AdminNudge {
  applicable: boolean
  sent_at: string | null
  available: boolean
  available_at: string | null
}

export interface AdminScholarshipDetail {
  id: number
  name: string
  school: string
  nric: string
  nric_verified: boolean
  mentoring_candidate: boolean
  verified_at: string | null
  verified_by: string
  verify_checklist: Record<string, boolean>
  profile_id: string | null
  // S13: typed-name signature captured at submit (used as a comparison against Vision-read IC name)
  declaration_name: string
  qualification: string
  spm_a_count: number | null
  merit_score: number | null
  stpm_pngk: number | null
  household_income: number | null
  household_size: number | null
  receives_str: boolean
  // Income wizard answers — drive the cockpit's route-aware income document panel.
  income_route?: string | null
  income_earner?: string | null
  income_working_members?: string[] | null
  /** TD-262: the per-earner "income SHOWN?" answer, served — see `@/lib/incomeShown`. Optional
   *  because the cockpit must keep working against an api revision that predates it. */
  income_shown?: IncomeShownMap | null
  receives_jkm: boolean
  intended_pathway: string
  intends_tertiary_2026: boolean
  aspirations: string
  plans: string
  fears: string
  justification: string
  // Profile-derived address (post-S14) — used by the admin Vision card to
  // cross-check what the student typed against the MyKad-read vision_address.
  address: string
  // Complete-profile view: contact + family + academic detail (profile-sourced)
  postal_code: string
  city: string
  preferred_state: string
  contact_phone: string
  contact_email: string
  notify_email: string
  verified_email: string
  preferred_call_language: string
  referral_source: string | null
  // Go-live transition (T2): the referring organisation (source) + the witness-org override.
  // referred_by_org null = sourceless (the cockpit then offers the witness dropdown).
  referred_by_org: { id: number; code: string; name: string } | null
  witness_org: { id: number; code: string; name: string } | null
  guardians: Array<{ name?: string; phone?: string; relationship?: string }>
  muet_band: number | null
  coq_score: number | null
  grades: Record<string, string>
  stpm_grades: Record<string, string>
  spm_prereq_grades: Record<string, string>
  // "Your story" narrative (S2) + support + declaration
  first_in_family: boolean
  parents_occupation: string
  siblings_studying_count: number | null
  // P2 (Check 2): the school/tertiary split — the family-burden breakdown
  siblings_in_school: number | null
  siblings_in_tertiary: number | null
  family_context: string
  daily_life: string
  consent_to_contact: boolean
  declared_at: string | null
  // My Plans + My Support intake (were exposed by the serializer; now typed)
  pathway_certainty: string
  chosen_pathway: string
  chosen_programme: Record<string, unknown> | null
  // Display split (card_display.programme_split): PISMP shows the constant degree as `title` +
  // the bidang as `stream`; STPM/Matric carry the track in `stream`; else `stream` is ''.
  chosen_programme_display?: { title: string; stream: string }
  pre_u_track: string
  pre_u_institution: string
  uncertainty_reasons: string[]
  uncertainty_note: string
  pathways_considered: string[]
  top_choices: Array<{ rank: number; course_id: string; course_name: string; institution: string }>
  upu_status: string
  field_of_study: string
  other_scholarships: string[]
  other_scholarships_text: string
  help_university: string
  help_scholarship: string
  anything_else: string
  status: string
  bucket: string
  shortlist_reason: string
  // Rejection bucket: '' | 'merit' | 'need' | 'ineligible' | 'interview' | 'contractual' | 'incomplete'
  rejection_category: string
  rejected_at: string | null
  rejected_by: string
  // The org-admin's verbatim reason ('incomplete' bucket only). Internal — never emailed.
  rejection_comments: string
  // The stored reporting date (ISO). Read the COLUMN, not the offer document's raw string —
  // the two used to be able to disagree, which is how a case displayed a ticked date while the
  // field driving its bursary was empty. Null when neither the letter nor an officer supplied it.
  reporting_date: string | null
  // Closure bucket: '' | 'graduated' | 'completed' | 'withdrawn' | 'lapsed' | 'terminated'
  closure_reason: string
  // Cool-off (#13/#14): a scheduled-but-unrevealed decline / award confirmation + its reveal date.
  pending_rejection_category: string
  decline_due_at: string | null
  award_due_at: string | null
  submitted_at: string
  funding_need: { categories: string[]; funding_note: string; programme_months: number | null } | null
  // S16 Phase A: deterministic pre-interview flag list. {code, params}; the
  // frontend resolves human copy from its i18n bundle (no server-side copy).
  anomalies: AdminAnomaly[]
  // V3 (#9): the interviewer's folded agenda (anomalies + open queries + needs-interview ambers
  // + a standing Motivation & grit section) so nothing raised at Check 1/2 evaporates at Check 3.
  interview_agenda: AdminAgendaEntry[]
  // S1 verification verdict: the four-fact rollup the coordinator audits.
  verdict: AdminVerdictFact[]
  // Check 2 STEP 1: the deterministic submission review — the facts ledger (claims +
  // how well each is backed), fundable-profile gaps, and consistency flags. Pure rules.
  submission_review: AdminSubmissionReview
  // Check 2 STEP 2/3: the query SLA clock + assignment readiness.
  query_sla: AdminQuerySla
  // Check 2: per-pathway funding-need estimate (the gap after govt coverage) for award sizing.
  funding_estimate: AdminFundingEstimate
  // Phase B: Gemini-suggested interview gaps. Carry their OWN dynamic text
  // (unlike anomalies which i18n by code). Empty until the admin generates them.
  interview_gaps: Array<{ code: string; question: string; why: string }>
  interview_gaps_run_at: string | null
  // Cockpit "verified value" reconciliation (2026-07-15): does the DOCUMENT-derived household
  // income / itemised roster corroborate the student's stated income + size? Drives the income /
  // household-size verified ticks. Non-mutating — a mismatch is flagged, never auto-applied.
  household_check?: {
    income: { documented_total: number | null; all_known: boolean; genuine?: boolean; stated: number | null; matches: boolean }
    // `confirmed`: the student answered the household_size_confirm query — the cockpit then shows
    // `described` (the roster count) with a tick + "Declared: {stated}" and uses it for per-capita.
    size: { described: number; stated: number | null; accounted: boolean; overcount: boolean; confirmed?: boolean }
  }
  documents: AdminApplicantDocument[]
  referees: AdminReferee[]
  consents: Array<{ id: number; consent_type: string; version: string; granted_by: string; guardian_name: string; guardian_relationship: string; is_active: boolean; granted_at: string }>
  sponsor_profile: AdminSponsorProfile | null
  // Phase C
  profile_completed_at: string | null
  completeness: AdminCompleteness
  // The exact consent gate (services.consent_blockers) — the SAME list the student's
  // submission enforces, so the officer's Blockers card and the student can never
  // disagree. Income codes are member-qualified ("parent_ic_missing:mother").
  // Empty = nothing outstanding.
  consent_blockers: string[]
  // The "you haven't submitted yet" reminder state (server-computed — see nudge.nudge_state).
  // Drives the Blockers-box reminder button; null-safe.
  nudge: AdminNudge
  interview_session: AdminInterviewSession | null
  assigned_to_id: number | null
  assigned_to_name: string | null
  assigned_at: string | null
  info_request_note: string
  info_requested_at: string | null
  // Sprint 5 — Verification verdict cockpit fields
  ai_verdict_snapshot: AdminVerdictFact[]
  officer_verdict: {
    identity?: string
    academic?: string
    income?: string
    pathway?: string
    overall?: string
  }
  verdict_reason: string
  verdict_decided_by: string
  verdict_decided_at: string | null
  /** Email of the QC (super/qc) who QC-Accepted → 'recommended'. Empty for cases recommended
   *  before this was captured (2026-07-08); the UI falls back to the reviewer accept stamp. */
  recommended_by: string
  /** Full names resolved from the stored reviewer emails (fall back to email in the UI). */
  verified_by_name: string
  verdict_decided_by_name: string
  recommended_by_name: string
  // The QC floor override: a super accepted this case over a RED fact, with a written reason.
  // Stored since the V5 gate shipped and surfaced nowhere until 2026-07-30.
  qc_override_by?: string
  qc_override_by_name?: string
  qc_override_at?: string | null
  qc_override_reason?: string
  rejected_by_name: string
  resolution_items: AdminResolutionItem[]
  /** Recommended assistance amount (RM, Decimal serialised as string) or null. */
  award_amount: string | null
  /** Standardised pathway-derived assistance (RM3,000 STPM / RM2,000 otherwise), auto-applied
   *  on approve. NULL when the verdict confidently disqualifies (see award_disqualifier);
   *  award_amount is the persisted (super-overridable) value. */
  proposed_award_amount: string | null
  /** When non-null, the confident-disqualifier verdict code that zeroed the proposal
   *  ('offer_not_official' | 'income_above_b40_line') — drives the cockpit "no amount" reason. */
  award_disqualifier: string | null
  /** Interview scheduling: booking state + proposed slots (dark behind the flag). */
  interview_schedule: InterviewSchedule
  /** Decision-reopen state: when set, the decision panel is editable + the reviewer
   *  dropdown unlocks + a "held from sponsors" banner shows; the reason drives the banner. */
  decision_reopened_at: string | null
  decision_reopen_reason: string
  /** The most recent reopen (open OR closed) — the audit anchor for the decision-history
   *  trail on a decided case (recommended by → reopened by, with reason → decided). Null when
   *  the case was never reopened. `reviewer_name` is the reviewer the reopen is attributed to
   *  (the original recommender). */
  last_decision_reopen: {
    reopened_by: string
    reopened_by_name: string
    reviewer_name: string
    reason: string
    created_at: string
    resulted_in_change: boolean
  } | null
  /** Internal-only corrections tally for the assigned reviewer (reopened decisions
   *  that led to a real change). Never shown on a sponsor/student surface. */
  assigned_to_corrections: number
  /** WHICH GIFT funds this case. The assignee picker uses it to grey a reviewer scoped to a
   *  different gift. ⚠ Not a fence — the org fence is server-side; a blank on either side
   *  greys nobody (see `officerCockpit.assignOptions`). */
  programme_id?: number | null
  /** Whether the dark-by-default Conditional Bursary Agreement feature is live; the cockpit
   *  only renders the agreement panel when true. */
  bursary_agreement_enabled?: boolean
  /** TD-144: the real loaded agreement (signature timestamps + status + PDF URL) so the
   *  cockpit shows accurate four-party ticks. Null when off / no agreement yet. No donor. */
  bursary_agreement?: BursaryAgreement | null
  /** Post-award S4: the money-out tranche ledger (oldest sequence first). */
  disbursements: AdminDisbursement[]
  /** Post-award S5: operational sub-state within status='maintenance'. */
  maintenance_substate: MaintenanceSubstate
  /** Post-award S6: manual-close audit (set when status='closed'). */
  closed_at: string | null
  closed_by: string
  /** Lifecycle transition stamps — the date the app FIRST reached each milestone
   *  (null until then). Drive the cockpit header timeline. */
  recommended_at: string | null
  awarded_at: string | null
  active_at: string | null
  maintenance_at: string | null
}

export interface AdminScholarshipListData {
  count: number
  total_count: number
  total_pages: number
  page: number
  page_size: number
  next: string | null
  previous: string | null
  applications: AdminScholarshipListItem[]
}

export async function getScholarshipApplications(
  filters: {
    status?: string
    bucket?: string
    source?: string
    assigned?: string
    q?: string
    page?: number
    pageSize?: number
    sort?: string
    dir?: string
    /** The gift the breadcrumb switcher is on. Omitted = every gift this caller may see —
     *  a real answer, not a missing one. The server re-fences the code on the caller's own
     *  organisation and 404s an unknown one; it is a narrowing, never a fence. */
    programme?: string
  } = {},
  options?: ApiOptions
) {
  const q = new URLSearchParams()
  if (filters.programme) q.set('programme', filters.programme)
  if (filters.status) q.set('status', filters.status)
  if (filters.bucket) q.set('bucket', filters.bucket)
  if (filters.source) q.set('source', filters.source)
  if (filters.assigned) q.set('assigned', filters.assigned)
  if (filters.q) q.set('q', filters.q)
  if (filters.sort) { q.set('sort', filters.sort); q.set('dir', filters.dir || 'asc') }
  if (filters.page && filters.page > 1) q.set('page', String(filters.page))
  if (filters.pageSize && filters.pageSize !== DEFAULT_ADMIN_PAGE_SIZE) {
    q.set('page_size', String(filters.pageSize))
  }
  const qs = q.toString()
  return adminFetch<AdminScholarshipListData>(
    `/api/v1/admin/scholarship/applications/${qs ? `?${qs}` : ''}`, options
  )
}

// ── Phase C: assignment, interview capture, request-more-docs ───────────────

/** Assign (or unassign with null) a reviewer to an application. F7: super-only,
 *  audited, gated on readiness for the first assignment. Throws with the server's
 *  `code` (not_ready / not_reviewer / bad_assignee) on a 400. */
export async function assignApplication(id: number, adminId: number | null, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/assign/`, 'POST', { reviewer_id: adminId }, options)
}

export async function requestMoreInfo(id: number, note: string, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/request-info/`, 'POST', { note }, options)
}

/** Active admins (for the assignment dropdown). Super admin only on the backend.
 *  `languages` = the codes (en/ms/ta) the reviewer is conversational+ in, for matching.
 *  `past_assignees` = anyone still on record as an application's assignee (org-fenced,
 *  independent of is_active/role) — the list filter's "Past reviewers" group. */
export async function getAssignableAdmins(options?: ApiOptions) {
  return adminFetch<{
    /** ⚠ A PAUSED reviewer is in this list, flagged — never filtered out. The cockpit unions the
     *  current assignee in from here, so dropping anybody makes their case read "Unassigned"
     *  (bug #66). The option renders DISABLED with "Paused" as the reason. */
    admins: Array<{
      id: number; name: string; email: string; role: string
      languages: string[]; corrections: number; paused: boolean
      /** Which gift they cover. **NULL = every gift** — the permissive default all 17
       *  org-scoped staff still carry, so a blank must never grey anybody out. Flagged the
       *  same way `paused` is: greyed with the gift named, never filtered out. */
      programme_id: number | null
      programme_name: string
    }>
    past_assignees?: Array<{ id: number; name: string }>
  }>(
    `/api/v1/admin/scholarship/assignable-admins/`, options)
}

export async function getScholarshipApplication(id: number, options?: ApiOptions) {
  return adminFetch<AdminScholarshipDetail>(`/api/v1/admin/scholarship/applications/${id}/`, options)
}

