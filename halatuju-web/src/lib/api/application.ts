/**
 * The bursary application itself: what it needs, what state it is in, and the intake (with
 * its per-gift apply copy) that it is made against.
 *
 * ⚠ TWO SPANS of the old `api.ts` (1472-1667 and 1744-1792). The interview calls sat in the
 * middle of the application's own functions; they are now `./interview`.
 */
import type { Locale } from '@/lib/branding'

import { apiRequest } from './client'
import type { ApiOptions } from './client'

// ── Scholarship (BrightPath Bursary Programme) ──────────────────────────────

export interface FundingNeed {
  // "How you'd use the support" — the S3 reframe (RM3,000 cap; tick-only categories
  // plus an open note plus rough programme length). The legacy per-line-item amount
  // fields were dropped in TD-059 cleanup.
  categories: string[]
  funding_note: string
  programme_months: number | null
}

export interface ApplicationCompleteness {
  quiz_done: boolean
  details_done: boolean
  funding_done: boolean
  documents_done: boolean
  consent_done: boolean
  address_done: boolean
  family_done: boolean
  complete: boolean
}

/**
 * What the programme asks this applicant for — resolved SERVER-SIDE (Layer 0, Sprint 3b).
 *
 * The codes are `ApplicantDocument.DOC_TYPES` values, with one deliberate exception:
 * `income_proof` is an AGGREGATE standing for the whole household-income route (STR vs salary,
 * per-member evidence). It is a switch over that engine, not a card — the engine itself stays on
 * the server and is never configurable document-by-document.
 *
 * Read this as data, never as a rule to re-derive. The front end used to keep its own list of
 * which documents were compulsory, and it disagreed with the submission gate in production.
 */
export interface ApplicationRequirements {
  documents: { required: string[]; optional: string[] }
  // Sprint 4 (2026-08-30): which QUESTIONS this programme asks — the story/funding/address
  // parts of the Step-4 wizard render from it. Optional for the same reason as the whole
  // block: a cached pre-Sprint-4 payload has no such key, and `questionRequirement()` in
  // `lib/scholarship.ts` decides the absent case once ('optional' — draw everything, assert
  // nothing compulsory). Go through that helper, never read this directly.
  questions?: { required: string[]; optional: string[] }
}

export interface ScholarshipApplication {
  id: number
  cohort_code: string
  cohort_name: string
  profile_id: string | null
  // Academic + financial fields are derived live from the canonical profile.
  exam_type?: 'spm' | 'stpm'
  spm_a_count: number | null
  stpm_pngk: number | null
  household_income: number | null
  household_size: number | null
  receives_str: boolean
  receives_jkm: boolean
  intended_pathway: string
  intends_tertiary_2026: boolean
  consent_to_contact: boolean
  status: string
  bucket: string
  shortlist_reason: string
  /** Post-award S5: operational sub-state within status='maintenance' (e.g. 'on_hold'). */
  maintenance_substate: 'on_track' | 'probation' | 'on_hold' | 'ready_to_close'
  /** Post-award S6: closure bucket — '' unless status='closed'. */
  closure_reason: '' | 'graduated' | 'completed' | 'withdrawn' | 'lapsed' | 'terminated'
  acknowledged_at: string | null
  submitted_at: string
  updated_at: string
  // Phase C: explicit confirm-submit timestamp + the admin's request-more-docs note
  profile_completed_at: string | null
  info_request_note: string
  info_requested_at: string | null
  aspirations: string
  plans: string
  fears: string
  justification: string
  // "Your story" guided narrative fields (S2 redesign)
  first_in_family: boolean
  parents_occupation: string
  // TD-061: the legacy siblings_studying boolean is gone; only the count remains.
  siblings_studying_count: number | null
  family_context: string
  daily_life: string
  // Structured family roster (redesign 2026-06) — the new inputs. first_in_family
  // + parents_occupation above are now DERIVED from these on the backend.
  father_name: string
  father_occupation: string
  father_occupation_other: string
  mother_name: string
  mother_occupation: string
  mother_occupation_other: string
  other_family_members: Array<{ role: 'brother' | 'sister' | 'guardian'; occupation: string; occupation_other?: string }>
  // Income Check-1 wizard answers (Documents → Household income).
  income_route: '' | 'str' | 'salary'
  income_earner: '' | 'father' | 'mother' | 'guardian' // STR route (single earner)
  // Salary route: the working household members (multi-select). Replaces the single
  // earner + work-status + other-earner for that route.
  income_working_members: Array<'father' | 'mother' | 'guardian' | 'brother' | 'sister'>
  // Phase 2A: declared informal income per working member ({member: RM/month}) — for a member
  // with no payslip; accepted with a valid STR, else needs an income_support_doc.
  income_declared?: Partial<Record<'father' | 'mother' | 'guardian' | 'brother' | 'sister', number>>
  // Phase 2B: unemployment detail per 'unemployed' roster member, {member: {reason, since}}.
  income_nonearning?: Partial<Record<'father' | 'mother' | 'guardian' | 'brother' | 'sister',
    { reason?: string; since?: string }>>
  earner_work_status: '' | 'payslip' | 'informal' | 'not_working' // deprecated (salary route)
  household_other_earners: number | null
  siblings_in_school: number | null
  siblings_in_tertiary: number | null
  // Address pre-fill from the profile (S14) — round-trips through the details
  // PATCH, but stored on the profile (state already came from /apply).
  address: string
  postal_code: string
  city: string
  preferred_state: string
  // Decided study (from /apply) — shown read-only on the Funding step so the
  // student sees what they're funding. Empty/uncertain when still exploring.
  pathway_certainty?: string
  chosen_pathway?: string
  chosen_programme?: { course_id?: string; course_name?: string; field_key?: string } | null
  pre_u_track?: string
  uncertainty_reasons?: string[]
  uncertainty_note?: string
  pre_u_institution?: string
  funding_need: FundingNeed | null
  completeness: ApplicationCompleteness
  /**
   * Layer 0 — what THIS programme asks for, resolved by the server.
   *
   * Optional on the type because a cached or partial payload from before Sprint 3b has no such
   * key; `documentRequirement()` in `lib/scholarship.ts` treats an absent block as "ask for
   * everything", never as "ask for nothing". Do NOT make it required and do NOT read it
   * directly — go through that helper, which is where the absent case is decided once.
   */
  requirements?: ApplicationRequirements
  notify_email?: string   // where decision/comms emails are sent (resolved at submit)
  contact_phone?: string  // profile phone — pre-fills the Vircle setup task's mobile field
  form_data: Record<string, unknown>
  intake_snapshot?: Record<string, unknown>   // frozen audit copy of what was declared at submit
  // F8b: set once the student finishes post-award onboarding (null until then).
  onboarded_at?: string | null
}

export async function submitScholarshipApplication(
  payload: Record<string, unknown>,
  lang: string = 'en',
  options?: ApiOptions
): Promise<ScholarshipApplication> {
  return apiRequest('/api/v1/scholarship/applications/', {
    method: 'POST',
    body: JSON.stringify({ ...payload, lang }),
    ...options,
  })
}

export async function getMyScholarshipApplications(
  options?: ApiOptions
): Promise<{ total_count: number; applications: ScholarshipApplication[] }> {
  return apiRequest('/api/v1/scholarship/applications/', options)
}

/** One open round a student may choose between. `code` is the PROGRAMME code — what `?p=` carries
 *  and what the server routes on. A cohort code is year-specific and would rot every intake. */
export interface IntakeChoice {
  code: string
  name: string
}

/** PUBLIC — whether NEW applications are open (drives the landing Apply button + the
 *  apply page). Existing applicants continue via their own application regardless.
 *
 *  ⚠ `choices` IS POPULATED ONLY WHEN THE SERVER CANNOT SAY WHICH ROUND — several are open and
 *  nothing named one. It is how the apply page ASKS before the form instead of letting the
 *  student discover the refusal at submit. Empty in every other case, including today's. */
/** One gift's own apply-page copy, per locale. Absent/empty = use the platform default. */
export interface ApplyCopyBlock {
  title: string
  intro: string
  criteria: string[]
}

export async function getScholarshipIntake(programme?: string): Promise<{
  open: boolean
  cohort_name: string
  choices?: IntakeChoice[]
  apply_copy?: Partial<Record<Locale, ApplyCopyBlock>>
}> {
  // ⚠ THE PROGRAMME CODE IS NOT OPTIONAL IN PRACTICE — pass it whenever the URL carries one.
  // Without it this asks "is anything open ANYWHERE?", which is a different question: with one
  // gift open and another closed, a student on the closed gift's own link was shown the whole
  // form and refused at submit. Sabah makes that reachable (2026-09-09).
  const code = (programme || '').trim()
  const qs = code ? `?programme=${encodeURIComponent(code)}` : ''
  return apiRequest(`/api/v1/scholarship/intake/${qs}`)
}

/** Fetch a single application (status + completeness + fields). Used to refresh
 *  page state after a document/consent change without losing in-progress edits. */
export async function getScholarshipApplication(
  id: number,
  options?: ApiOptions
): Promise<ScholarshipApplication> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/`, { ...options })
}

export async function updateScholarshipDetails(
  id: number,
  payload: Record<string, unknown>,
  options?: ApiOptions
): Promise<ScholarshipApplication> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    ...options,
  })
}

/** Student self-serve income route switch (post-submit Action Centre). Flips the
 *  income route (STR ↔ salary), recomputes the document tasks, and returns the new
 *  route + its requirements. Never re-blocks the submission. */
export async function switchIncomeRoute(
  id: number,
  body: { income_route: 'str' | 'salary'; income_earner?: string; income_working_members?: string[] },
  options?: ApiOptions
): Promise<{ income_route: string; requirements: { route: string; members: unknown[]; compulsory: string[]; optional: string[] } }> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/income-route/`, {
    method: 'POST',
    body: JSON.stringify(body),
    ...options,
  })
}

/** Phase C: the student's explicit "Confirm & submit" action. Resolves to the
 *  updated application (status → profile_complete). Throws on 400
 *  incomplete_profile (the error carries the completeness breakdown). */
export async function confirmScholarshipApplication(
  id: number,
  options?: ApiOptions
): Promise<ScholarshipApplication> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/confirm/`, {
    method: 'POST',
    ...options,
  })
}

