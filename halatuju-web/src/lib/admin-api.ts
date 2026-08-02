/**
 * Admin API client for partner organisations.
 *
 * All endpoints require Supabase auth and return 403 if the user
 * is not a partner admin.
 */

import type {
  AcademicCheck, PathwayCheck, IncomeIcCheck, IncomeProofCheck,
  StrCheck, UtilityCheck, BcCheck, GuardianshipCheck, SupportDocCheck, SemesterCheck,
  SchoolLeavingCheck, BursaryAgreement,
} from '@/lib/api'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ApiOptions {
  token?: string
}

async function adminFetch<T>(path: string, options?: ApiOptions): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}${path}`, { headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Admin API error: ${res.status}`)
  }

  return res.json()
}

// ── Types ────────────────────────────────────────────────────────────

export interface DashboardData {
  org_name: string
  org_code: string | null
  total_students: number
  completed_onboarding: number
  by_exam_type: Record<string, number>
  top_fields: Array<{ field: string; count: number }>
}

export interface StudentListItem {
  supabase_user_id: string
  name: string
  nric: string
  gender: string
  exam_type: string
  school: string
  contact_phone: string
  referral_source: string | null
  org_name: string | null
  owning_org_name?: string | null
  created_at: string
}

export interface StudentListData {
  org_name: string
  is_super_admin: boolean
  count: number
  total_pages: number
  page: number
  page_size: number
  next: string | null
  previous: string | null
  students: StudentListItem[]
  /** Distinct referral_source values across the admin's visible set, for the Source filter. */
  source_options: string[]
}

export interface StudentDetailData {
  supabase_user_id: string
  name: string
  nric: string
  angka_giliran: string
  gender: string
  nationality: string
  contact_phone: string
  address: string
  postal_code: string
  city: string
  school: string
  household_income: number | null
  household_size: number | null
  colorblind: string
  disability: string
  exam_type: string
  grades: Record<string, string>
  stpm_grades: Record<string, string>
  stpm_cgpa: number | null
  muet_band: number | null
  student_signals: Record<string, unknown>
  preferred_state: string
  financial_pressure: string
  travel_willingness: string
  referral_source: string | null
  org_name: string | null
  created_at: string
  saved_courses: Array<{ course_id: string; name: string }>
}

// ── API functions ────────────────────────────────────────────────────

export async function getPartnerDashboard(options?: ApiOptions) {
  return adminFetch<DashboardData>('/api/v1/admin/dashboard/', options)
}

export const DEFAULT_ADMIN_PAGE_SIZE = 25

export async function getPartnerStudents(
  params?: { page?: number; pageSize?: number; q?: string; exam?: string; source?: string },
  options?: ApiOptions,
) {
  const qs = new URLSearchParams()
  if (params?.page && params.page > 1) qs.set('page', String(params.page))
  if (params?.pageSize && params.pageSize !== DEFAULT_ADMIN_PAGE_SIZE) {
    qs.set('page_size', String(params.pageSize))
  }
  if (params?.q) qs.set('q', params.q)
  if (params?.exam) qs.set('exam', params.exam)
  if (params?.source) qs.set('source', params.source)
  const query = qs.toString()
  return adminFetch<StudentListData>(
    `/api/v1/admin/students/${query ? `?${query}` : ''}`,
    options,
  )
}

export async function getPartnerStudent(userId: string, options?: ApiOptions) {
  return adminFetch<StudentDetailData>(
    `/api/v1/admin/students/${userId}/`,
    options
  )
}

export function getExportUrl() {
  return `${API_BASE}/api/v1/admin/students/export/`
}

export async function deleteStudent(userId: string, options?: ApiOptions) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/students/${userId}/`, {
    method: 'DELETE',
    headers,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Delete failed: ${res.status}`)
  }

  return res.json()
}

// ── Admin management ────────────────────────────────────────────────

export interface AdminItem {
  id: number
  name: string
  email: string
  is_super_admin: boolean
  role: 'super' | 'admin' | 'org_admin' | 'partner' | 'reviewer' | 'qc' | 'finance'
  is_active: boolean
  org_name: string | null
  owning_org_id?: number | null
  owning_org_name?: string | null
  created_at: string
}

export async function getAdmins(options?: ApiOptions) {
  return adminFetch<{ admins: AdminItem[] }>('/api/v1/admin/admins/', options)
}

export async function revokeAdmin(adminId: number, action: 'revoke' | 'restore', options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/revoke/`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ action }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(body.error || `Action failed: ${res.status}`) as Error & { code?: string }
    err.code = body.code || body.error || ''
    throw err
  }
  return res.json()
}

/** Re-send a partner's sign-in details, rotating their temporary password. The new password goes
 *  ONLY to their inbox — it is never returned here. Safe to call any number of times. */
export async function resendAdminInvite(adminId: number, options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/resend/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Resend failed: ${res.status}`)
  }
  return res.json() as Promise<{ message: string; emailed: boolean }>
}

// A temp-password partner sets their OWN password server-side (the service role applies it without
// the re-auth the client updateUser({password}) would demand). Scoped to the caller + must_change_password.
export async function adminSetPassword(password: string, options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/set-password/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Set password failed: ${res.status}`)
  }
  return res.json() as Promise<{ ok: boolean }>
}

// ── Admin profile ───────────────────────────────────────────────────

export interface AdminProfile {
  id: number
  name: string
  email: string
  is_super_admin: boolean
  org_name: string | null
  org_contact_person: string | null
  org_phone: string | null
}

export async function getAdminProfile(options?: ApiOptions) {
  return adminFetch<AdminProfile>('/api/v1/admin/profile/', options)
}

export async function updateAdminProfile(
  data: { name?: string; org_contact_person?: string; org_phone?: string },
  options?: ApiOptions
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/profile/`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Update failed: ${res.status}`)
  }
  return res.json()
}

// ── Reviewer profile (F6) ───────────────────────────────────────────
// A reviewer's own credentials + contact details. Self-scoped endpoint
// (always the calling admin's own row). phone/address are private staff
// PII — reviewer + super only, never exposed to students/sponsors.

export interface ReviewerProfile {
  highest_qualification: string
  university: string
  graduation_year: number | null
  field_of_study: string
  phone: string
  address: string
  street_address: string
  postcode: string
  city: string
  state: string
  english_fluency: LangFluency
  bm_fluency: LangFluency
  tamil_fluency: LangFluency
  share_phone_with_students: boolean
  /**
   * Whether this reviewer has stepped back from NEW work.
   *
   * ⚠ Stored on `PartnerAdmin`, NOT on the profile row — assignment reads the admin record, and a
   * second copy here would be a second truth to drift. It rides on this payload because one screen
   * owns "how I take part". `paused_at` is read-only; PATCH `paused` to change it.
   */
  paused: boolean
  paused_at?: string | null
}

export type LangFluency = '' | 'conversational' | 'fluent'

export async function getReviewerProfile(options?: ApiOptions) {
  return adminFetch<ReviewerProfile>('/api/v1/admin/reviewer-profile/', options)
}

export async function updateReviewerProfile(
  data: Partial<ReviewerProfile>,
  options?: ApiOptions
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/reviewer-profile/`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Update failed: ${res.status}`)
  }
  return res.json() as Promise<ReviewerProfile>
}

// ── Invite / Orgs ───────────────────────────────────────────────────

export interface OrgItem {
  id: number
  code: string
  name: string
  contact_person: string
  phone: string
}

export async function getOrgs(options?: ApiOptions) {
  return adminFetch<{ orgs: OrgItem[] }>('/api/v1/admin/orgs/', options)
}

// ── Sources (referral organisations) + witness assignment (go-live transition) ──
// The Sources registry reuses PartnerOrganisation.phone / contact_person / contact_email
// (NOT a separate contact_phone column). super/org_admin only.

export interface SourceItem {
  id: number
  code: string
  name: string
  contact_person: string
  contact_email: string
  phone: string
  show_in_apply: boolean
  is_active: boolean
  student_count: number | null
}

export async function getSources(options?: ApiOptions) {
  return adminFetch<{ sources: SourceItem[] }>('/api/v1/admin/scholarship/sources/', options)
}

export async function createSource(
  data: {
    code: string; name: string; contact_person?: string; contact_email?: string
    phone?: string; show_in_apply?: boolean
  },
  options?: ApiOptions,
) {
  return adminMutate<SourceItem>('/api/v1/admin/scholarship/sources/', 'POST', data, options)
}

export async function updateSource(
  id: number,
  data: Partial<{
    name: string; contact_person: string; contact_email: string; phone: string
    show_in_apply: boolean; is_active: boolean
  }>,
  options?: ApiOptions,
) {
  return adminMutate<SourceItem>(`/api/v1/admin/scholarship/sources/${id}/`, 'PATCH', data, options)
}

// ── Partner emails (2026-07-26) ───────────────────────────────────────────
// Five programme-wide emails to the referral organisations that run this bursary alongside us.
// One switch per email — on means every QUALIFYING partner receives it; there is no
// per-organisation choice (owner ruling).

export interface PartnerEmailTemplate {
  kind: string
  enabled: boolean
  /** True for the one email on this screen the STUDENT receives, not the partner organisation. */
  to_student: boolean
  subject: string
  body: string
  placeholders: string[]
  updated_by_email: string
  updated_at: string | null
  last_sent_at: string | null
  last_sent_orgs: number
}

export interface PartnerEmailOrg {
  id: number
  code: string
  name: string
  students: number
  has_email: boolean
  is_house_org: boolean
  qualifies: boolean
}

export interface PartnerEmailsPayload {
  templates: PartnerEmailTemplate[]
  organisations: PartnerEmailOrg[]
  /** How many organisations an email would actually reach today. */
  qualifying_count: number
  /** Referral partners in total — the house organisation is not one of them. */
  partner_count: number
  /** The platform flag. Settings still save while it is off; nothing sends. */
  comms_enabled: boolean
}

// ---- Sponsor comms (S3, 2026-07-28) ----
// The twin of the partner-email pair. One switch per EMAIL, not per sponsor: a sponsor is not a
// tenant, and "which donors hear about a new student" is not a per-donor decision.

export interface SponsorEmailTemplate {
  kind: string
  /** The model's own human label for the kind — the panel prefers its i18n copy. */
  label: string
  enabled: boolean
  subject: string
  body: string
  placeholders: string[]
  updated_by_email: string
  updated_at: string | null
  last_sent_at: string | null
  last_sent_count: number
}

export interface SponsorEmailsPayload {
  templates: SponsorEmailTemplate[]
  /** The PLATFORM gate. Switches still save while it is off; nothing sends. */
  comms_enabled: boolean
  /** Seeded vs expected — a mismatch means the seed command has not been run. */
  seeded: number
  expected: number
  sponsor_count: number
}

export async function getSponsorEmails(options?: ApiOptions): Promise<SponsorEmailsPayload> {
  return adminFetch('/api/v1/admin/scholarship/sponsor-emails/', options)
}

export async function updateSponsorEmail(
  kind: string,
  patch: { enabled?: boolean; subject?: string; body?: string },
  options?: ApiOptions,
): Promise<SponsorEmailTemplate> {
  return adminMutate(`/api/v1/admin/scholarship/sponsor-emails/${kind}/`, 'PATCH', patch, options)
}

// ── Sponsor terms (T2) ───────────────────────────────────────────────────────
// The versioned document a sponsor accepts. Authoring only — nothing here is sponsor-facing.

export interface SponsorTermsSection {
  order: number
  heading_en: string; heading_ms: string; heading_ta: string
  body_en: string; body_ms: string; body_ta: string
  is_quiz_candidate: boolean
  /** `{tag, plain, question, options[3], correct, why}` — the same shape the student quiz uses. */
  quiz_en: SponsorQuizPayload
  quiz_ms: SponsorQuizPayload
  quiz_ta: SponsorQuizPayload
  /** Blank = hand-written. Otherwise the model that drafted it. */
  quiz_generated_model: string
}

export interface SponsorQuizPayload {
  tag?: string
  plain?: string
  question?: string
  options?: string[]
  correct?: number
  why?: string
}

export interface SponsorTermsSummary {
  id: number
  version: string
  status: 'draft' | 'active' | 'archived'
  title_en: string
  /** Locales servable WHOLE — the table's Languages column. */
  languages_available: string[]
  section_count: number
  created_by_email: string
  published_by_email: string
  published_at: string | null
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface SponsorTermsDetail extends SponsorTermsSummary {
  title_ms: string; title_ta: string
  intro_en: string; intro_ms: string; intro_ta: string
  sections: SponsorTermsSection[]
  acceptance_count: number
}

export interface SponsorTermsRule { code: string; label: string }
export interface SponsorTermsValidation {
  ok: boolean
  errors: SponsorTermsRule[]
  warnings: SponsorTermsRule[]
}

export interface SponsorTermsListPayload {
  versions: SponsorTermsSummary[]
  active_version: string
  sponsor_count: number
}

const ST = '/api/v1/admin/scholarship/sponsor-terms'

export async function getSponsorTermsList(options?: ApiOptions): Promise<SponsorTermsListPayload> {
  return adminFetch(`${ST}/`, options)
}

export async function getSponsorTerms(id: number, options?: ApiOptions): Promise<SponsorTermsDetail> {
  return adminFetch(`${ST}/${id}/`, options)
}

export async function createSponsorTerms(
  body: { version: string; copy_from?: number },
  options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/`, 'POST', body, options)
}

export async function updateSponsorTermsIntro(
  id: number,
  patch: Partial<Pick<SponsorTermsDetail,
    'title_en' | 'title_ms' | 'title_ta' | 'intro_en' | 'intro_ms' | 'intro_ta'>>,
  options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/${id}/`, 'PATCH', patch, options)
}

export async function putSponsorTermsSections(
  id: number,
  sections: Array<Partial<SponsorTermsSection>>,
  options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/${id}/sections/`, 'PUT', { sections }, options)
}

export async function generateSponsorTermsQuiz(
  id: number, order: number, options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/${id}/sections/${order}/generate-quiz/`, 'POST', {}, options)
}

export async function validateSponsorTerms(
  id: number, options?: ApiOptions,
): Promise<SponsorTermsValidation> {
  return adminFetch(`${ST}/${id}/validate/`, options)
}

export async function publishSponsorTerms(
  id: number, options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/${id}/publish/`, 'POST', {}, options)
}

/**
 * Propose a flat section list from an author's .docx. PROPOSAL ONLY — nothing is saved, and the
 * upload is never retained. Sub-clauses fold into their parent's body (owner, 2026-07-28).
 */
export async function importSponsorTermsDocx(
  id: number, file: File, options?: ApiOptions,
): Promise<{
  title: string
  intro: string
  sections: Array<Pick<SponsorTermsSection, 'heading_en' | 'body_en' | 'is_quiz_candidate' | 'quiz_en'>>
}> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}${ST}/${id}/import-docx/`, {
    method: 'POST', headers, body: form,
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    const err = new Error(b.error || `Import failed: ${res.status}`) as Error & { code?: string }
    err.code = b.error || ''
    throw err
  }
  return res.json()
}

export async function previewSponsorTerms(
  id: number, locale: string, options?: ApiOptions,
): Promise<{
  document: {
    version: string; locale_used: string; title: string; intro: string
    sections: Array<{ order: number; heading: string; body: string; has_quiz: boolean }>
  }
  checkpoints: Array<SponsorQuizPayload & { order: number }>
}> {
  return adminFetch(`${ST}/${id}/preview/?locale=${encodeURIComponent(locale)}`, options)
}

export async function getPartnerEmails(options?: ApiOptions) {
  return adminFetch<PartnerEmailsPayload>('/api/v1/admin/scholarship/partner-emails/', options)
}

export async function updatePartnerEmail(
  kind: string,
  data: Partial<{ enabled: boolean; subject: string; body: string }>,
  options?: ApiOptions,
) {
  return adminMutate<PartnerEmailTemplate>(
    `/api/v1/admin/scholarship/partner-emails/${kind}/`, 'PATCH', data, options)
}

/** Assign (code/id) or clear (null) the witness-organisation override for an application. */
export async function assignWitness(
  applicationId: number, witnessOrg: string | number | null, options?: ApiOptions,
) {
  return adminMutate<{ id: number; witness_org: string | null; witness_org_name: string | null }>(
    `/api/v1/admin/scholarship/applications/${applicationId}/witness/`, 'PATCH',
    { witness_org: witnessOrg }, options)
}

export async function inviteAdmin(
  data: {
    email: string
    name: string
    role?: 'admin' | 'partner' | 'reviewer' | 'qc' | 'org_admin' | 'finance'
    org_id?: number
    new_org_name?: string
    new_org_code?: string
    contact_person?: string
    org_phone?: string
  },
  options?: ApiOptions
) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/invite/`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Invite failed: ${res.status}`)
  }

  // `emailed` matters: the welcome email is the ONLY carrier of the temporary password, so a
  // failed send leaves the new partner with no way in until the owner presses Resend.
  return res.json() as Promise<{
    message: string
    org: string | null
    role: string
    already_registered: boolean
    emailed: boolean
  }>
}

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
  // done OR the 5-day window lapsed. The dropdown disables a FIRST assignment while false — the
  // detail cockpit's firstAssignBlocked, mirrored so the list can't offer an assign the server refuses.
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

export type MaintenanceSubstate = 'on_track' | 'probation' | 'on_hold' | 'ready_to_close'
export type ClosureReason = 'graduated' | 'completed' | 'withdrawn' | 'lapsed' | 'terminated'

/** Post-award S4: one disbursement tranche. Admin-facing — funder link by id only,
 *  never a sponsor identity (anonymity holds). */
export interface AdminDisbursement {
  id: number
  sequence: number
  amount: string
  status: 'scheduled' | 'due' | 'released' | 'withheld' | 'returned'
  label: string
  scheduled_for: string | null
  released_at: string | null
  actioned_by: string
  reference: string
  note: string
  sponsorship_id: number | null
  created_at: string
}

export type DisbursementAction = 'release' | 'withhold' | 'return' | 'mark_due'

/** One proposed interview time. `start` is ISO (UTC); render in MYT on the client. */
export interface InterviewSlot {
  id: number
  start: string
  duration_min: number
  is_active: boolean
}

/** Interview booking state + the active proposed slots (shared admin/student shape). */
export interface InterviewSchedule {
  enabled: boolean
  status: '' | 'booked' | 'cancelled'
  start: string | null
  meeting_url: string
  meeting_provider: string
  booked_slot_id: number | null
  slots: InterviewSlot[]
  reschedule_cutoff_hours: number
  /** Reviewer-facing only: start times (ISO) this reviewer already holds for OTHER
   *  students, so the propose grid can grey them out. Absent on the student payload. */
  reviewer_busy?: string[]
  /** The student said none of the proposed times work and asked for others. */
  alternatives_requested?: boolean
  alternatives_note?: string
  cancel_reason?: string
  /** The student's messages to their reviewer (the always-open channel), oldest first. */
  messages?: { text: string; created_at: string }[]
}

/** Admin-facing resolution item. Mirrors the student-facing ResolutionItem in
 *  src/lib/api.ts but kept separate — do not cross-import. */
export interface AdminResolutionItem {
  id: number
  fact: string
  code: string
  // boolean supports flags like `needs_officer_eye` (the circuit-breaker escalation).
  params: Record<string, string | number | boolean | string[]>
  prompt: string
  kind: 'doc' | 'confirm' | 'explanation'
  doc_type: string
  status: string
  source: 'system' | 'officer'
  resolution_text: string
  created_at: string
  resolved_at: string | null
}

/** Verdict metrics summary returned by GET /verdict-metrics/. */
export interface VerdictMetrics {
  applications: number
  fact_decisions: number
  overrides: number
  override_rate: number
  per_fact: Record<string, { decided: number; overrides: number }>
}

async function adminMutate<T>(path: string, method: string, body: unknown, options?: ApiOptions): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method, headers, body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    const err = new Error(b.error || `Admin API error: ${res.status}`) as Error
      & { status?: number; code?: string; body?: Record<string, unknown> }
    err.status = res.status
    err.code = b.code || b.error || ''
    // Keep the whole error body: some codes carry a detail the UI needs to render a useful
    // message rather than restate a rule (e.g. 'too_early' → `earliest`, the first date a run
    // covering that month may be paid, computed by payments.earliest_payment_date).
    err.body = b
    throw err
  }
  return res.json()
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
  } = {},
  options?: ApiOptions
) {
  const q = new URLSearchParams()
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

export async function getInterview(id: number, options?: ApiOptions) {
  return adminFetch<{ session: AdminInterviewSession | null; agenda: string[] }>(
    `/api/v1/admin/scholarship/applications/${id}/interview/`, options)
}

export async function saveInterview(
  id: number,
  payload: { findings: Record<string, { verdict: string; rationale: string }>; rubric: Record<string, number>; overall_note: string },
  options?: ApiOptions,
) {
  return adminMutate<AdminInterviewSession>(
    `/api/v1/admin/scholarship/applications/${id}/interview/`, 'POST', payload, options)
}

export async function submitInterview(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/interview/submit/`, 'POST', {}, options)
}

/** Reopen a SUBMITTED interview (un-submits → draft) so the reviewer can add a forgotten
 *  finding; reopens both the Interview Stage and Check 2. Only valid before a decision. */
export async function reopenInterview(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/interview/reopen/`, 'POST', {}, options)
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
    }>
    past_assignees?: Array<{ id: number; name: string }>
  }>(
    `/api/v1/admin/scholarship/assignable-admins/`, options)
}

/**
 * Step a reviewer back from NEW work, or bring them back — the admin's route (super/org_admin).
 *
 * The reviewer's own route is a `paused` field on their profile PATCH. Both go through one service,
 * so "paused" cannot mean two things depending on who pressed it.
 */
export async function setReviewerPaused(id: number, paused: boolean, options?: ApiOptions) {
  return adminMutate<{ id: number; paused: boolean; paused_at: string | null }>(
    `/api/v1/admin/reviewers/${id}/pause/`, 'POST', { paused }, options)
}

/** Reverse a recorded decision (super-only): holds the sponsor profile from the pool
 *  and unlocks the decision panel. `reason` is required (a reopen asserts a reviewer error). */
export async function reopenDecision(id: number, reason: string, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/reopen-decision/`, 'POST', { reason }, options)
}

/** Close a reopen with NO change — restore the profile to its prior published state. */
export async function cancelReopen(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/cancel-reopen/`, 'POST', {}, options)
}

/** QC gate on an AWAITING-QC ('interviewed') case: accept → recommended, or reopen → back to
 *  the reviewer at 'interviewing' (comments emailed to the assigned reviewer).
 *  override_reason: super-only pass of the V5 verdict gap floor — recorded server-side. */
export async function recordQcDecision(
  id: number,
  payload: { decision: 'accept' | 'reopen' | 'reject'; comments?: string; override_reason?: string },
  options?: ApiOptions,
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/qc-decision/`, 'POST', payload, options)
}

export async function getScholarshipApplication(id: number, options?: ApiOptions) {
  return adminFetch<AdminScholarshipDetail>(`/api/v1/admin/scholarship/applications/${id}/`, options)
}

/** Check-2 case summary — the LLM briefing above the verdict checklist. `enabled:false` when the
 *  feature flag is off (dark); `summary:''` when every fact is Certain (nothing to brief). */
export interface VerdictCaseSummary {
  enabled: boolean
  summary?: string
  cached?: boolean
  model?: string
  error?: string
}
export async function getVerdictCaseSummary(id: number, options?: ApiOptions) {
  return adminFetch<VerdictCaseSummary>(
    `/api/v1/admin/scholarship/applications/${id}/verdict-summary/`, options)
}

// ── Interview scheduling (reviewer proposes times) ────────────────────────────
/** The assigned reviewer (or super) proposes interview times. `starts` are ISO
 *  strings. Returns the refreshed schedule (booking state + active slots). */
export async function proposeInterviewSlots(
  id: number, starts: string[], options?: ApiOptions & { reschedule?: boolean }) {
  const { reschedule, ...rest } = options || {}
  return adminMutate<InterviewSchedule>(
    `/api/v1/admin/scholarship/applications/${id}/interview-slots/`, 'POST',
    { slots: starts, ...(reschedule ? { reschedule: true } : {}) }, rest)
}

export async function getInterviewSlots(id: number, options?: ApiOptions) {
  return adminFetch<InterviewSchedule>(
    `/api/v1/admin/scholarship/applications/${id}/interview-slots/`, options)
}

/** Withdraw a single proposed (unbooked) slot. */
export async function withdrawInterviewSlot(id: number, slotId: number, options?: ApiOptions) {
  return adminMutate<InterviewSchedule>(
    `/api/v1/admin/scholarship/applications/${id}/interview-slots/${slotId}/`, 'DELETE', null, options)
}

/** Phase B: admin-on-demand Gemini interview gap-spotter. Returns the refreshed detail.
 *  ``append`` generates 3 MORE (without repeating) and appends; otherwise replaces. */
export async function suggestInterviewGaps(
  id: number, language?: string, options?: ApiOptions, append = false
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/suggest-gaps/`, 'POST',
    { ...(language ? { language } : {}), ...(append ? { append: true } : {}) }, options
  )
}

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

// ── Conditional Bursary Award Agreement (admin actions) ─────────────────────
// A thin POST helper that carries the HTTP status on the thrown error so the
// cockpit card can surface a 403 (e.g. a non-referring-org admin trying to
// witness) gracefully, rather than as a generic failure.
async function adminBursaryPost(path: string, body: unknown, options?: ApiOptions): Promise<BursaryAgreement> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST', headers, body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    const err = new Error(b.error || `Admin API error: ${res.status}`) as Error & { status?: number; code?: string }
    err.status = res.status
    err.code = b.error || b.code || ''
    throw err
  }
  return res.json()
}

/** The Foundation countersignature on a student's bursary agreement. SUPER-ONLY
 *  (the backend gates it). Returns the updated agreement (Foundation now signed). */
export async function adminCountersignBursary(applicationId: number, options?: ApiOptions): Promise<BursaryAgreement> {
  return adminBursaryPost(
    `/api/v1/admin/scholarship/applications/${applicationId}/bursary-agreement/countersign/`, {}, options)
}

/** The partner organisation's (non-blocking) witness attestation. The backend
 *  allows the referring-org admin or a super; anyone else gets a 403 (surfaced
 *  via err.status === 403). `witnessName` is the optional named signatory. */
export async function adminWitnessBursary(
  applicationId: number, witnessName?: string, options?: ApiOptions,
): Promise<BursaryAgreement> {
  return adminBursaryPost(
    `/api/v1/admin/scholarship/applications/${applicationId}/bursary-agreement/witness/`,
    witnessName ? { witness_name: witnessName } : {}, options)
}

/** S16 Phase A: deterministic pre-interview flag (anomaly engine). The `code`
 *  resolves to two i18n keys: `scholarship.admin.anomaly.{code}.fact` (the
 *  observed inconsistency, with `params` interpolated) and `.question` (the
 *  suggested interview question). */
export interface AdminAnomaly {
  code: string
  params: Record<string, string | number>
}

/** V3 (#9): a folded interview-agenda entry. kind: anomaly (pre-interview flag) ·
 *  open_query (a carried-over unanswered query, ask verbally) · needs_interview (a verdict
 *  amber that says "confirm at interview") · motivation (the standing Motivation & grit
 *  section; params.seeded=true when the statement of intent is thin). */
export interface AdminAgendaEntry {
  code: string
  kind: 'anomaly' | 'open_query' | 'needs_interview' | 'motivation'
  params: Record<string, string | number | boolean>
}

/** S1 verification verdict. One of four facts the coordinator AUDITS (does not
 *  assemble). Each evidence/unresolved item's `code` resolves to
 *  `admin.scholarship.verdict.item.{code}` in i18n (params interpolate).
 *  status: verified (green, AI asserts) · review (amber, confirm) ·
 *  recommend (blue, a human places the verdict) · gap (red, action needed). */
export interface AdminVerdictItem {
  // string[] supports the income reason codes' `members` list (e.g. ['father','brother']).
  code: string
  params: Record<string, string | number | string[]>
}
export interface AdminVerdictFact {
  fact: 'identity' | 'academic' | 'income' | 'pathway'
  status: 'verified' | 'review' | 'recommend' | 'gap'
  evidence: AdminVerdictItem[]
  unresolved: AdminVerdictItem[]
}

/** Check 2 STEP 1 — the deterministic submission review. */
export interface AdminLedgerRow {
  claim: string
  value: string
  source: string
  // verified (assert as fact) · reported (self-reported / under review) ·
  // student_words (their voice) · unverified (omit or hedge).
  verification: 'verified' | 'reported' | 'student_words' | 'unverified'
}
export interface AdminSubmissionReview {
  ledger: AdminLedgerRow[]
  completeness: Array<{ code: string }>
  consistency: AdminAnomaly[]
}

/** Check 2 — per-pathway funding-need estimate (RM [low, high]). */
export interface AdminFundingEstimate {
  pathway: string            // 'stpm' | 'matric' | 'asasi' | 'poly' | 'university' | 'pismp' | 'unknown'
  known: boolean             // false for an un-estimated/unknown pathway → fall back to self-report
  monthly: number            // est. RM monthly shortfall after govt allowance + PTPTN
  months: number | null      // typical (or student-stated) programme length
  total: number              // monthly × months, rounded to RM100 — the whole-programme need
  variable: boolean          // cost varies a lot by institution/field → show a caveat
  practical: boolean         // has an internship/practical term that may add travel
}

/** Check 2 STEP 2/3 — the query SLA clock for the cockpit. */
export interface AdminQuerySla {
  deadline: string | null
  lapsed: boolean
  open_count: number
  days_left: number | null
  ready_for_assignment: boolean
  // true when the app is proceeding to assignment WITH clarify queries still open
  // (the SLA lapsed) — the 'ready-with-open-queries' reviewer flag.
  proceeding_with_open_queries: boolean
  // V3 (#7): higher-priority clarify gaps crowded out by the cap right now (0 = none) — the
  // cockpit shows "N more queries waiting" so a capped-out query stays visible to the officer.
  clarify_overflow: number
}

export interface AdminApplicantDocument {
  id: number
  doc_type: string
  // Salary-route income docs: whose IC/salary slip/EPF this is (father/mother/…); '' otherwise.
  household_member?: string
  // Officer box placement: the stored tag, or (for a blank-tagged income doc) the member resolved
  // from the name on the doc against the family roster. '' for non-income / unresolvable. The
  // cockpit places a doc by `resolved_member || household_member`.
  resolved_member?: string
  original_filename: string
  content_type: string
  size: number
  verification_status: string
  download_url: string | null
  // S13: Vision OCR soft-signal fields (populated only for doc_type='ic')
  // Post-S14: vision_address surfaced for admin cross-check, no matcher.
  vision_nric: string
  vision_name: string
  vision_address: string
  vision_run_at: string | null
  vision_error: string
  vision_nric_verdict: '' | 'match' | 'mismatch' | 'unreadable'
  vision_name_verdict: '' | 'match' | 'partial' | 'mismatch' | 'unreadable'
  // Supporting-doc soft name/address presence checks (results slip, income, bills…)
  vision_name_match: '' | 'found' | 'not_found' | 'unreadable'
  vision_address_match: '' | 'found' | 'not_found' | 'unreadable'
  // Document-assist: Gemini-extracted fields for admin verification.
  // S2: results_slip carries `results: [{subject, grade}]` (subject+grade pairs).
  vision_fields?: {
    fields?: Record<string, string | string[] | Array<{ subject?: string; grade?: string }>>
    warnings?: string[]
    student_verdict?: string
    // How this doc's fields were read: 'deterministic' (label-anchored parser) vs 'ai'
    // (Gemini fallback) — surfaced to the officer as a capture-confidence badge.
    capture?: 'deterministic' | 'ai'
    error?: string
  }
  // Per-fact verification checks (the admin detail serializes documents via
  // ApplicantDocumentSerializer, so these arrive on the admin response too). Each is
  // null unless its doc_type matches. The cockpit renders them as coloured fact-labels.
  academic_check?: AcademicCheck | null
  pathway_check?: PathwayCheck | null
  income_ic_check?: IncomeIcCheck | null
  income_proof_check?: IncomeProofCheck | null
  str_check?: StrCheck | null
  utility_check?: UtilityCheck | null
  bc_check?: BcCheck | null
  guardianship_check?: GuardianshipCheck | null
  support_doc_check?: SupportDocCheck | null
  semester_check?: SemesterCheck | null
  school_leaving_check?: SchoolLeavingCheck | null
  // Genuineness fingerprint (soft, flag-gated) — for ic/parent_ic/str/results_slip/birth_certificate/
  // epf/offer_letter. Null when the check didn't run. The cockpit uses it to colour the doc chip.
  authenticity?: { status: 'genuine' | 'likely_genuine' | 'suspect' | `not_${string}`; reason: string; doc_seen?: string } | null
  // Phase 2 version history: when this doc was replaced by a re-upload (null/absent = the
  // live copy) + which doc superseded it. The admin serializer returns superseded rows so the
  // cockpit can show them under an "Old / Replaced" list; they are excluded from every fact group.
  superseded_at?: string | null
  superseded_by?: number | null
}

/** Admin re-runs Vision OCR on an existing IC document (soft signal, never a gate). */
export async function reRunVision(id: number, docId: number, options?: ApiOptions) {
  return adminMutate<AdminApplicantDocument>(
    `/api/v1/admin/scholarship/applications/${id}/documents/${docId}/re-run-vision/`,
    'POST', {}, options
  )
}

export interface AdminReferee {
  id: number; name: string; role: string; relationship: string; phone: string; email: string
}

/** Coordinator records a referee for the application at the verify-&-accept stage. */
export async function addReferee(
  id: number,
  payload: { name: string; role?: string; relationship?: string; phone?: string; email?: string },
  options?: ApiOptions
) {
  return adminMutate<AdminReferee>(
    `/api/v1/admin/scholarship/applications/${id}/referees/`, 'POST', payload, options
  )
}

/** Remove a referee from the application (204 No Content on success). */
export async function deleteReferee(id: number, refId: number, options?: ApiOptions): Promise<void> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(
    `${API_BASE}/api/v1/admin/scholarship/applications/${id}/referees/${refId}/`,
    { method: 'DELETE', headers }
  )
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    throw new Error(b.error || `Admin API error: ${res.status}`)
  }
}

// ── Sprint 5: Officer verdict + caveats ─────────────────────────────────────

export interface RecordVerdictPayload {
  officer_verdict: {
    identity?: string
    academic?: string
    income?: string
    pathway?: string
    overall?: string
  }
  reason?: string
  finalise?: boolean
  language?: string
}

export interface RecordVerdictResult extends AdminScholarshipDetail {
  finalise_result: { ok: boolean; code?: string } | null
}

/** Record the coordinator's verdict. May also trigger a final-profile
 *  generation when `finalise: true` is passed. */
export async function recordVerdict(
  id: number,
  payload: RecordVerdictPayload,
  options?: ApiOptions,
): Promise<RecordVerdictResult> {
  return adminMutate<RecordVerdictResult>(
    `/api/v1/admin/scholarship/applications/${id}/record-verdict/`,
    'POST',
    payload,
    options,
  )
}

/** Aggregate override-rate metrics for the verdict engine.
 *  `cohort` is optional; omit to get the cross-cohort totals. */
export async function getVerdictMetrics(
  options?: ApiOptions,
  cohort?: string,
): Promise<VerdictMetrics> {
  const qs = cohort ? `?cohort=${encodeURIComponent(cohort)}` : ''
  return adminFetch<VerdictMetrics>(
    `/api/v1/admin/scholarship/verdict-metrics/${qs}`,
    options,
  )
}

/** Coordinator raises a new resolution item (free-text or doc request) for the
 *  student's Action Centre. */
export async function raiseResolutionItem(
  id: number,
  payload: { kind: 'doc' | 'confirm' | 'explanation'; prompt: string; doc_type?: string; fact?: string; household_member?: string },
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/resolution-items/`,
    'POST',
    payload,
    options,
  )
}

/** Waive, resolve, or reopen ("Ask again") a resolution item on behalf of the coordinator. */
export async function actionResolutionItem(
  itemId: number,
  action: 'waive' | 'resolve' | 'reopen',
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/resolution-items/${itemId}/${action}/`,
    'POST',
    {},
    options,
  )
}

/** Set (or clear with null) the recommended assistance amount the reviewer proposes. */
export async function setAwardAmount(
  id: number,
  amount: number | null,
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/award-amount/`,
    'POST',
    { amount },
    options,
  )
}

// ── Post-award S4: disbursement/tranche ledger ──
export async function scheduleTranche(
  id: number,
  payload: { amount: number | string; sequence?: number; label?: string; scheduled_for?: string | null },
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/disbursements/`,
    'POST',
    payload,
    options,
  )
}

export async function actOnDisbursement(
  disbursementId: number,
  action: DisbursementAction,
  payload?: { note?: string },
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/disbursements/${disbursementId}/${action}/`,
    'POST',
    payload ?? {},
    options,
  )
}

// ── Post-award S5: maintenance sub-state ──
export async function setMaintenanceSubstate(
  id: number,
  substate: MaintenanceSubstate,
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/maintenance/`,
    'POST',
    { substate },
    options,
  )
}

// ── Post-award S6: manual closure ──
export async function closeApplication(
  id: number,
  closureReason: ClosureReason,
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/close/`,
    'POST',
    { closure_reason: closureReason },
    options,
  )
}

// ── Phase E: sponsor account vetting ──
export interface AdminSponsor {
  id: number
  name: string
  email: string
  phone: string
  source: string
  organisation: string
  note: string
  status: 'pending' | 'approved' | 'rejected' | 'suspended'
  reviewed_at: string | null
  reviewed_by: string
  created_at: string
  /** Confirmed money, ORG-FENCED (a tenant sees its own share). Always a 2dp string. */
  given: string
  /** Students this sponsor is currently holding money for. Fenced the same way `given` is. */
  students: number
  /** Null until this sponsor next opens their portal — nothing recorded it before 2026-07-27. */
  last_seen_at: string | null
}

/** One wallet. The sponsor's money is per (sponsor, programme) — never a single pooled figure. */
export interface AdminSponsorWallet {
  programme_id: number | null
  programme_name: string
  given: string
  committed: string
  available: string
  credits: number
  students: number
}

export interface AdminSponsorCredit {
  id: number
  programme_id: number | null
  programme_name: string
  amount: string
  source: string
  external_reference: string
  status: 'draft' | 'admin_signed' | 'finance_checked' | 'confirmed' | 'cancelled'
  is_spendable: boolean
  recorded_by: string
  recorded_at: string | null
  finance_checked_by: string
  finance_checked_at: string | null
  confirmed_by: string
  confirmed_at: string | null
  created_at: string
}

export interface AdminSponsorStudent {
  id: number
  application_id: number
  /** The ANONYMOUS code the sponsor sees — the vocabulary both sides share. */
  ref: string
  programme_name: string
  amount: string
  status: string
  offered_at: string | null
  decided_at: string | null
}

/**
 * One sponsor, whole. The ACCOUNT is platform-level and shown in full; the money and the
 * students are fenced to the caller's organisation — `fenced` says which you are looking at.
 */
export interface AdminSponsorDetail {
  id: number
  name: string
  email: string
  phone: string
  organisation: string
  source: string
  note: string
  status: 'pending' | 'approved' | 'rejected' | 'suspended'
  is_trusted: boolean
  created_at: string
  reviewed_at: string | null
  reviewed_by: string
  last_seen_at: string | null
  consent_at: string | null
  consent_version: string
  notify_frequency: 'realtime' | 'weekly' | 'off'
  last_digest_sent_at: string | null
  programmes: AdminSponsorWallet[]
  credits: AdminSponsorCredit[]
  sponsorships: AdminSponsorStudent[]
  referrals: Array<{
    id: number
    invitee_name: string
    invitee_email: string
    status: string
    created_at: string
    joined_at: string | null
  }>
  memberships: Array<{
    /** Null only on a legacy row with no programme; the credit form skips those. */
    programme_id: number | null
    programme_name: string
    status: string
    vetted_by: string
    vetted_at: string | null
  }>
  /** Live, never stored — appointing a finance admin arms the credit chain's middle step. */
  finance_check_required: boolean
  /** True when this caller sees only their own organisation's share of the account. */
  fenced: boolean
}

export async function getSponsorDetail(id: number, options?: ApiOptions): Promise<AdminSponsorDetail> {
  return adminFetch(`/api/v1/admin/sponsors/${id}/`, options)
}

export async function listSponsors(status?: string, options?: ApiOptions): Promise<{ sponsors: AdminSponsor[] }> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return adminFetch(`/api/v1/admin/sponsors/${q}`, options)
}

/** Lean count of sponsor accounts awaiting vetting — drives the nav + Administration-hub badge. */
export async function getPendingSponsorCount(options?: ApiOptions): Promise<{ count: number }> {
  return adminFetch('/api/v1/admin/sponsors/pending-count/', options)
}

export async function reviewSponsor(
  id: number, action: 'approve' | 'reject' | 'suspend', options?: ApiOptions
): Promise<AdminSponsor> {
  return adminMutate(`/api/v1/admin/sponsors/${id}/review/`, 'POST', { action }, options)
}

// ---- Wallet credits (P4b endpoints, live since 2026-07-27; UI added in sponsor S2) ----
// These three have existed and been org-fenced on the server since P4b; until now nothing
// called them, so every credit was keyed in by a developer. The chain is
// draft → admin_signed → [finance_checked] → confirmed, and `sign` posts to ONE endpoint
// whichever step is next — the service decides which, so the client never names a step.

/** Record an off-platform gift as a `draft`. `external_reference` is the bank ref, mandatory. */
export async function recordSponsorCredit(
  body: { sponsor_id: number; programme_id: number; amount: string; external_reference: string },
  options?: ApiOptions,
): Promise<AdminSponsorCredit> {
  return adminMutate('/api/v1/admin/scholarship/credits/', 'POST', body, options)
}

/** Sign whichever step is next. The typed name must match the caller's own admin record. */
export async function signSponsorCredit(
  id: number, typedName: string, options?: ApiOptions,
): Promise<AdminSponsorCredit> {
  return adminMutate(`/api/v1/admin/scholarship/credits/${id}/sign/`, 'POST',
    { typed_name: typedName }, options)
}

/** Void an UNCONFIRMED credit. The row is kept — a confirmed credit is never cancelled. */
export async function voidSponsorCredit(
  id: number, options?: ApiOptions,
): Promise<AdminSponsorCredit> {
  return adminMutate(`/api/v1/admin/scholarship/credits/${id}/cancel/`, 'POST', null, options)
}

// ---- Requests space (Sprint 15) ----
// Bug/feature requests → AI reviewer → owner-gated hours quotes. Dark behind REQUESTS_ENABLED:
// every route 404s while off, which is how the Administration hub card ships dark (the count
// probe 404s → the card is hidden; no client flag).

/**
 * One entry in a request's DISCUSSION (TD-201) — the replacement for the `clarifications`
 * question/answer pairs, which are no longer on either payload.
 *
 * A QUESTION IS A COMMENT AWAITING A REPLY (`awaiting_reply`), which is what makes this one
 * stream rather than a thread of questions with a separate comment log beside it.
 *
 * ⚠ `visibility: 'internal'` NEVER reaches an org_admin — the server filters the ROWS out of the
 * org payload (`org_requests.comments_for`). It appears in this type because the SUPER payload
 * carries both, and the detail page badges an internal comment so the owner can see at a glance
 * what the requester cannot. Do not treat its absence client-side as the protection; the
 * protection is server-side and tested there.
 */
export interface OrgRequestComment {
  id: number
  // WHO spoke. 'ai' is the reviewer and 'engineer' is the approved analysis (TD-204) — neither has
  // a PartnerAdmin row, so `author_name` is '' for both.
  // ⚠ Every value here needs `admin.requests.detail.author.<kind>` in en/ms/ta: the thread renders
  // that key from the value, so a missing one prints a raw dotted path to the requester.
  author_kind: 'ai' | 'owner' | 'org' | 'engineer'
  author_name: string
  body: string
  visibility: 'shared' | 'internal'
  awaiting_reply: boolean
  created_at: string
}

/** A screenshot attached to a request (Sprint 15.1). download_url is a signed Supabase URL or
 *  null (denied when the blob's key-org disagrees with the request's org). */
export interface OrgRequestAttachment {
  id: number
  original_filename: string
  content_type: string
  size: number
  created_at: string
  download_url: string | null
}

/**
 * The engineer's working paper behind one comment (TD-204) — **OWNER-ONLY**.
 *
 * ⚠ This never appears on an org_admin's payload. The analysis reaches the requesting organisation
 * as PROSE, through `comments`, authored `engineer`; the CITED FILES and the ENGINEER'S HOURS stay
 * owner-side. Neither is secrecy: a citation the requester cannot open buys them nothing while the
 * paths disclose the internal shape of a multi-tenant platform, and a second hours figure in front
 * of them recreates what removing the AI's estimate fixed. The field is optional on
 * `OrgRequestDetail` for exactly that reason — an org payload does not carry it at all.
 */
export interface OrgRequestAnalysis {
  id: number
  body: string
  estimated_hours: string | null
  cited_files: string[]
  authored_by: string
  repo_sha: string
  /** The engineer's PROPOSED triage. It prefills the owner's form and applies nothing — the
   *  request's own kind/lane change only when the owner presses Run. '' means "no opinion",
   *  which is not the same as agreeing with the AI draft. */
  proposed_kind: string
  proposed_lane: string
  created_at: string
  approved_at: string | null
  approved_by_name: string
  superseded_at: string | null
  /** The one the quote gate reads — server-computed, so the screen and the gate cannot disagree. */
  is_current: boolean
}

/** The ORG-facing payload (what a submitting org_admin sees) — the allowlist. NEVER carries the
 *  AI draft (ai_*) or the owner's triage. The owner (super) additionally receives the owner
 *  fields below (all optional here). */
export interface OrgRequestDetail {
  id: number
  kind: string
  title: string
  description: string
  // Optional Bugzilla-style scoping (owner-approved Sprint 15 increment); '' when unset.
  component: string
  urgency: string
  steps_to_reproduce: string
  status: string
  // The discussion, oldest first. Filtered to `shared` for an org_admin, server-side.
  comments: OrgRequestComment[]
  attachments: OrgRequestAttachment[]
  quote_hours: string | null
  quote_note: string
  quoted_at: string | null
  approved_at: string | null
  scheduled_for: string | null
  decline_reason: string
  created_at: string
  updated_at: string
  submitted_by_name: string
  // Owner-only (super payload) — undefined in the org payload by construction.
  organisation_id?: number
  organisation_name?: string
  // The margin is owner-only (owner, 2026-07-30: "do not mention the margin"). It is off the ORG
  // serializer entirely, not merely hidden in the UI, so an org payload cannot carry it.
  quote_margin_pct?: number | null
  // The engineer's analyses, newest first (TD-204). Owner-only — see OrgRequestAnalysis.
  analyses?: OrgRequestAnalysis[]
  ai_run_count?: number
  ai_draft_kind?: string
  ai_draft_lane?: string
  ai_draft_hours?: string | null
  ai_draft_note?: string
  ai_draft_model?: string
  ai_draft_at?: string | null
  triaged_kind?: string
  lane?: string
  triage_note?: string
  triaged_at?: string | null
  declined_by_role?: string
}

export async function getOrgRequests(
  filters?: { status?: string }, options?: ApiOptions
): Promise<{ requests: OrgRequestDetail[] }> {
  const qs = filters?.status ? `?status=${encodeURIComponent(filters.status)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/requests/${qs}`, options)
}

export async function getOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminFetch(`/api/v1/admin/scholarship/requests/${id}/`, options)
}

/** The lean badge probe. 404s while REQUESTS_ENABLED is off → callers hide the hub card. */
export async function getOrgRequestCount(options?: ApiOptions): Promise<{ count: number }> {
  return adminFetch('/api/v1/admin/scholarship/requests/count/', options)
}

// ── Billing & usage v1 (Sprint 13a) ──────────────────────────────────────────
export interface BillingServiceRow {
  service: string
  events: number
  quantity: number
  input_tokens: number
  output_tokens: number
}

export interface BillingOrgBlock {
  organisation_id: number | null
  organisation: string
  is_platform: boolean
  services: BillingServiceRow[]
  totals: { events: number; quantity: number; input_tokens: number; output_tokens: number }
  storage_bytes: number
}

export interface BillingUsagePayload {
  month: string
  months: string[]
  can_see_platform: boolean
  organisations: BillingOrgBlock[]
}

/** The super/org_admin usage readout. 404s while BILLING_USAGE_ENABLED is off (dark ship) →
 * callers show a "coming soon" placeholder rather than the live card. `month` = 'YYYY-MM'. */
export async function getBillingUsage(
  options?: ApiOptions & { month?: string }
): Promise<BillingUsagePayload> {
  const q = options?.month ? `?month=${encodeURIComponent(options.month)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/billing/usage/${q}`, options)
}

export async function createOrgRequest(
  data: {
    kind: string; title: string; description: string; organisation_id?: number
    component?: string; urgency?: string; steps_to_reproduce?: string
  },
  options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate('/api/v1/admin/scholarship/requests/', 'POST', data, options)
}

// Requestee (org_admin) actions
export async function answerOrgRequest(
  id: number, data: { answer: string; index?: number }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/answer/`, 'POST', data, options)
}
/**
 * The OWNER asks the requester a question — the other half of the clarification thread, which
 * until 2026-07-30 only the AI could write to. Super-only server-side.
 */
export async function askOrgRequest(
  id: number, data: { question: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/ask/`, 'POST', data, options)
}
/**
 * Post to the DISCUSSION (TD-201) — a STATEMENT, not a question, so it awaits no reply and does
 * not spend the reviewer's question budget.
 *
 * Open to the super AND to any org_admin of the owning organisation: they can already read the
 * request, so this lets the people already in the room speak rather than only watch.
 *
 * `visibility: 'internal'` is SUPER-ONLY — the server answers 403 for anyone else, and an org
 * author can never be internal at all. Omit it for the ordinary shared case.
 */
export async function commentOrgRequest(
  id: number, data: { body: string; visibility?: 'shared' | 'internal' }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/comments/`, 'POST', data, options)
}
/**
 * Stage the engineer's analysis as a DRAFT (TD-204). Super-only; posts nothing.
 *
 * Normally written by the `record_request_analysis` management command, which additionally checks
 * that every cited path exists in the repo. This client exists so the same thing can be done from
 * the cockpit — but a citation typed here is NOT existence-checked, which is the command's whole
 * advantage.
 */
export async function recordOrgRequestAnalysis(
  id: number,
  data: { body: string; estimated_hours?: string; cited_files: string[]; authored_by?: string },
  options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/analysis/`, 'POST', data, options)
}
/** The owner approves an analysis and it enters the thread as an `engineer` comment. Super-only. */
export async function approveOrgRequestAnalysis(
  id: number, analysisId: number, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/analysis/${analysisId}/approve/`,
                     'POST', {}, options)
}
/** Retire a DRAFT analysis the engineer got wrong, so it cannot be approved by mistake. */
export async function withdrawOrgRequestAnalysis(
  id: number, analysisId: number, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/analysis/${analysisId}/withdraw/`,
                     'POST', {}, options)
}
export async function approveOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/approve/`, 'POST', {}, options)
}
export async function deferOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/defer/`, 'POST', {}, options)
}
export async function modifyOrgRequest(
  id: number, data: { description: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/modify/`, 'POST', data, options)
}
export async function declineOrgRequest(
  id: number, data: { reason?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/decline/`, 'POST', data, options)
}

// Owner (super) actions
export async function triageOrgRequest(
  id: number, data: { triaged_kind: string; lane: string; note?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/triage/`, 'POST', data, options)
}
export async function quoteOrgRequest(
  id: number, data: { hours: number; margin_pct?: number; note?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/quote/`, 'POST', data, options)
}
export async function requoteOrgRequest(
  id: number, data: { hours: number; margin_pct?: number; note?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/requote/`, 'POST', data, options)
}
export async function scheduleOrgRequest(
  id: number, data: { scheduled_for?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/schedule/`, 'POST', data, options)
}
export async function doneOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/done/`, 'POST', {}, options)
}
export async function aiRerunOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/ai-rerun/`, 'POST', {}, options)
}

// ---- Screenshot attachments (Sprint 15.1) ----
// The upload is the sign -> PUT bytes to Supabase -> record chain (ActionCentre.tsx:187 pattern);
// see uploadOrgRequestAttachment for the whole flow.
async function signOrgRequestAttachment(
  id: number, options?: ApiOptions
): Promise<{ upload_url: string; storage_path: string }> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/attachments/sign-upload/`, 'POST', {}, options)
}

async function recordOrgRequestAttachment(
  id: number,
  payload: { storage_path: string; original_filename: string; content_type: string; size: number },
  options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/attachments/`, 'POST', payload, options)
}

export async function deleteOrgRequestAttachment(
  id: number, attId: number, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/attachments/${attId}/`, 'DELETE', null, options)
}

/** The whole upload chain: sign → PUT the bytes straight to Supabase → record the row. Returns the
 *  refreshed request (with the new attachment). Throws on any step (caller shows a warning). */
export async function uploadOrgRequestAttachment(
  id: number, file: File, options?: ApiOptions
): Promise<OrgRequestDetail> {
  const { upload_url, storage_path } = await signOrgRequestAttachment(id, options)
  const resp = await fetch(upload_url, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': file.type || 'application/octet-stream', 'x-upsert': 'true' },
  })
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`)
  return recordOrgRequestAttachment(id, {
    storage_path,
    original_filename: file.name,
    content_type: file.type || 'application/octet-stream',
    size: file.size,
  }, options)
}

// ---- Course Data dashboard (read-only) ----

export interface LinkFailure {
  url: string
  kind: string          // 'gone' | 'dns' | 'timeout' | 'conn' | 'badurl' | …
  detail: string        // HTTP code for 'gone'
  institutions: string[]
  refs: number          // how many catalogue rows use this URL
}

export interface CourseDataStatusEntry {
  last_run_at: string | null
  // counts (numbers) + the link-health 'failures' array; kept loose for forward-compat.
  summary: Record<string, number | string> & { failures?: LinkFailure[] }
  detail: string
}

export interface CourseDataCoverage {
  spm_total: number
  spm_by_source: Record<string, number>
  stpm_total: number
  stpm_active: number
  tvet_have: number
  uptvet_available: number | null
  uptvet_gap: number | null
  emasco_total: number
}

export interface CourseDataStatusResponse {
  statuses: Record<string, CourseDataStatusEntry | null>
  coverage: CourseDataCoverage
}

export async function getCourseDataStatus(options?: ApiOptions): Promise<CourseDataStatusResponse> {
  return adminFetch<CourseDataStatusResponse>('/api/v1/admin/course-data/', options)
}

/** Run the read-only health check (audit + link reachability) now; returns the refreshed status. */
export async function runCourseDataCheck(options?: ApiOptions): Promise<CourseDataStatusResponse> {
  return adminMutate<CourseDataStatusResponse>('/api/v1/admin/course-data/check/', 'POST', {}, options)
}

// ── Payments module (P2): monthly Vircle payment runs ─────────────────────────
export interface PaymentRunSummary {
  id: number
  reference: string
  payment_date: string
  /** The month this run pays for (1st of month, ISO); dedup key — a student is paid once per month. */
  period_month: string | null
  status: 'draft' | 'admin_signed' | 'finance_checked' | 'completed' | 'cancelled'
  students: number
  total: string
  created_at: string
}
export interface PaymentRunItem {
  id: number
  application_id: number
  name: string
  nric: string
  vircle_id: string
  /** Advisory: has Vircle activated this eWallet (mirrored from the relay sheet)? A false value
   *  shows a "not yet activated" chip — it never blocks; the student stays payable regardless. */
  activated: boolean
  award_amount: string
  paid_to_date: string
  amount: string
  credit_applied: string
  included: boolean
  exclude_reason: string
}
export interface PaymentRunSkipped {
  application_id: number
  name: string
  nric: string
  reasons: string[]
}
export interface PaymentSignature { name: string; email: string; at: string }
export interface PaymentRunDetail {
  /** Where the payment instruction is emailed on countersignature (shown in the declaration). */
  vircle_email?: string
  id: number
  reference: string
  payment_date: string
  /** The month this run pays for (1st of month, ISO); dedup key — a student is paid once per month. */
  period_month: string | null
  status: 'draft' | 'admin_signed' | 'finance_checked' | 'completed' | 'cancelled'
  note: string
  drive_file_url: string
  created_by: string
  created_at: string
  admin_signed: PaymentSignature | null
  /** The middle CHECKER signature. Null on every run made before the finance role existed and
   *  on every run in an org with no active finance admin — render those as the 2-card layout. */
  finance_signed: PaymentSignature | null
  /** Whether THIS org's chain includes the finance check. Computed by the server
   *  (payments.finance_check_required) and read verbatim — NEVER re-derive it here from the
   *  staff list, or the activation rule becomes a keep-in-sync pair that drifts. */
  finance_check_required: boolean
  org_admin_signed: PaymentSignature | null
  items: PaymentRunItem[]
  skipped: PaymentRunSkipped[]
  students: number
  total: string
}

/** One student's line in the Payments funding summary. Mirrors the backend's
 *  FundingSummaryRowSerializer, which is an explicit allowlist — the only student data a
 *  `finance` admin can reach. Nothing identifying beyond the name, and no documents, income
 *  or verdicts; the backend pins the exact key set with a snapshot test. */
export interface FundingSummaryRow {
  application_id: number
  name: string
  ref: string
  status: string
  pathway: string
  award_amount: string
  paid_to_date: string
  remaining: string
  vircle_id: string
  last_run: { reference: string; payment_date: string } | null
}
export interface FundingSummary {
  rows: FundingSummaryRow[]
  totals: { students: number; award_total: string; paid_total: string; remaining_total: string }
}
export async function getFundingSummary(options?: ApiOptions) {
  return adminFetch<FundingSummary>('/api/v1/admin/scholarship/payments/funding-summary/', options)
}

export async function getPaymentRuns(options?: ApiOptions) {
  return adminFetch<{ runs: PaymentRunSummary[] }>('/api/v1/admin/scholarship/payment-runs/', options)
}
export async function createPaymentRun(payment_date: string, payment_month: string, options?: ApiOptions) {
  return adminMutate<PaymentRunDetail>('/api/v1/admin/scholarship/payment-runs/', 'POST', { payment_date, payment_month }, options)
}
export async function getPaymentRun(id: number, options?: ApiOptions) {
  return adminFetch<PaymentRunDetail>(`/api/v1/admin/scholarship/payment-runs/${id}/`, options)
}
export async function updatePaymentRunItem(
  runId: number, itemId: number,
  patch: { included?: boolean; exclude_reason?: string; amount?: string },
  options?: ApiOptions,
) {
  return adminMutate<PaymentRunDetail>(
    `/api/v1/admin/scholarship/payment-runs/${runId}/items/${itemId}/`, 'PATCH', patch, options)
}
export async function signPaymentRun(id: number, typed_name: string, options?: ApiOptions) {
  return adminMutate<PaymentRunDetail>(
    `/api/v1/admin/scholarship/payment-runs/${id}/sign/`, 'POST', { typed_name }, options)
}
export async function cancelPaymentRun(id: number, options?: ApiOptions) {
  return adminMutate<PaymentRunDetail>(
    `/api/v1/admin/scholarship/payment-runs/${id}/cancel/`, 'POST', {}, options)
}
/** Fetch the run CSV (auth header required) and return its text for a client-side download. */
export async function fetchPaymentRunCsv(id: number, options?: ApiOptions): Promise<string> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/scholarship/payment-runs/${id}/csv/`, { headers })
  if (!res.ok) throw new Error(`CSV download failed: ${res.status}`)
  return res.text()
}

// ── Contract module (S4) — org-owned versioned bursary templates ───────────────
export type ContractStatus = 'draft' | 'pending_deployment' | 'active' | 'archived'

export interface ContractQuizPayload {
  tag?: string; plain?: string; question?: string
  options?: string[]; correct?: number; why?: string
}

export interface ContractClauseData {
  order: number
  level: number   // 0 clause, 1 sub-clause, 2 sub-sub-clause (numbers computed from the level run)
  heading_en: string; heading_ms: string; heading_ta: string
  body_en: string; body_ms: string; body_ta: string
  is_quiz_candidate: boolean
  quiz_en: ContractQuizPayload; quiz_ms: ContractQuizPayload; quiz_ta: ContractQuizPayload
  quiz_generated_model: string
}

export interface ContractScheduleRowData {
  pathway: string; variant: string
  label_en: string; label_ms: string; label_ta: string
  monthly_amount: string; start_month: number
  paid_offsets: number[]; sort_order: number
  months: number; total: string
}

export interface ContractTemplateSummary {
  id: number; organisation: string; version: string; status: ContractStatus
  languages_available: string[]
  vetted_by_name: string; vetted_on: string | null
  deployed_by_at: string | null; created_at: string; updated_at: string
}

export interface ContractTemplateDetail extends ContractTemplateSummary {
  title_en: string; title_ms: string; title_ta: string
  preamble_en: string; preamble_ms: string; preamble_ta: string
  progress_standard_en: string; progress_standard_ms: string; progress_standard_ta: string
  counterparty_name: string; counterparty_title: string; counterparty_nric: string
  counterparty_address: string
  counterparty_notify_emails: string[]
  parent_role: 'co_signer_all' | 'minor_only'
  parent_pin_required: boolean
  witness_policy: 'none' | 'optional' | 'required'
  vetting_attested_by_email: string; vetting_attested_at: string | null
  created_by_email: string; submitted_by_email: string; submitted_by_at: string | null
  deployed_by_email: string; archived_at: string | null
  clauses: ContractClauseData[]
  schedule: ContractScheduleRowData[]
}

export interface ContractValidation {
  ok: boolean
  errors: Array<{ code: string; label: string }>
  warnings: Array<{ code: string; label: string }>
}

const CT = '/api/v1/admin/scholarship/contract-templates'

export async function getContractTemplates(organisation?: string, options?: ApiOptions) {
  const q = organisation ? `?organisation=${encodeURIComponent(organisation)}` : ''
  return adminFetch<{ templates: ContractTemplateSummary[] }>(`${CT}/${q}`, options)
}
export async function createContractTemplate(
  body: { version: string; organisation?: string; copy_from?: number }, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/`, 'POST', body, options)
}
export async function getContractTemplate(id: number, options?: ApiOptions) {
  return adminFetch<ContractTemplateDetail>(`${CT}/${id}/`, options)
}
export async function updateContractConfig(id: number, patch: Record<string, unknown>, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/`, 'PATCH', patch, options)
}
export async function putContractClauses(
  id: number, clauses: Array<Partial<ContractClauseData>>, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/clauses/`, 'PUT', { clauses }, options)
}
export async function putContractSchedule(
  id: number, rows: Array<Partial<ContractScheduleRowData>>, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/schedule/`, 'PUT', { rows }, options)
}
export async function generateContractQuiz(id: number, order: number, options?: ApiOptions) {
  return adminMutate<ContractClauseData>(`${CT}/${id}/clauses/${order}/generate-quiz/`, 'POST', {}, options)
}
export async function recordContractVetting(
  id: number, body: { vetted_by_name: string; vetted_on: string }, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/vetting/`, 'POST', body, options)
}
export async function getContractValidation(id: number, options?: ApiOptions) {
  return adminFetch<ContractValidation>(`${CT}/${id}/validate/`, options)
}
export async function submitContractTemplate(id: number, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/submit/`, 'POST', {}, options)
}
export async function revertContractTemplate(id: number, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/revert/`, 'POST', {}, options)
}
export async function deployContractTemplate(id: number, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/deploy/`, 'POST', {}, options)
}
export async function getContractQuizPreview(id: number, locale: string, options?: ApiOptions) {
  return adminFetch<{ template_version: string; locale_used: string; checkpoints: ContractQuizPayload[] }>(
    `${CT}/${id}/quiz-preview/?locale=${encodeURIComponent(locale)}`, options)
}
/** The rendered preview HTML (for an iframe srcDoc). Auth header required. */
export async function fetchContractPreviewHtml(id: number, locale: string, options?: ApiOptions): Promise<string> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${CT}/${id}/preview/?locale=${encodeURIComponent(locale)}`, { headers })
  if (!res.ok) throw new Error(`Preview failed: ${res.status}`)
  return res.text()
}
/** Import a .docx → a PROPOSED [{heading, body, level}] clause list (nothing saved; file not retained). */
export async function importContractDocx(
  id: number, file: File, options?: ApiOptions): Promise<{
    clauses: Array<{ heading: string; body: string; level: number }>
    title: string; preamble: string
    counterparty?: { name?: string; nric?: string; address?: string }
  }> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}${CT}/${id}/import-docx/`, { method: 'POST', headers, body: form })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    const err = new Error(b.error || `Import failed: ${res.status}`) as Error & { status?: number; code?: string }
    err.status = res.status
    err.code = b.code || b.error || ''
    throw err
  }
  return res.json()
}

/** The rendered preview PDF as a Blob (auth header required) — for a client-side open.
 *  Uses ?output=pdf, NOT ?format=pdf — `format` is DRF's reserved content-negotiation
 *  param and `?format=pdf` 404s before the view runs (TD-163). */
export async function fetchContractPreviewPdf(id: number, locale: string, options?: ApiOptions): Promise<Blob> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${CT}/${id}/preview/?locale=${encodeURIComponent(locale)}&output=pdf`, { headers })
  if (!res.ok) throw new Error(`Preview PDF failed: ${res.status}`)
  return res.blob()
}

// ── nav/IA N3a: the breadcrumb switchers ─────────────────────────────────────
/** One organisation or programme the caller may LOOK AT. */
export interface AdminScopeOrg { id: number; code: string; name: string }
export interface AdminScopeProgramme extends AdminScopeOrg { organisation_id: number }
export interface AdminScopes {
  organisations: AdminScopeOrg[]
  programmes: AdminScopeProgramme[]
}

/**
 * What this admin may look at — feeds the breadcrumb switchers.
 *
 * ⚠ NOT an access check and must never be used as one. The answer is derived server-side from
 * the same `owning_organisation` the org fence uses, so it cannot widen anything; a client that
 * ignores it reaches exactly the same data. The selection it produces is a DISPLAY preference —
 * it must not travel as a header, a cookie, or anything ambient, because that would relocate the
 * fence into the client.
 *
 * Never throws upward in the shell: a switcher is furniture, and a failed fetch must not take
 * the console down. Callers treat a rejection as "no scopes to offer".
 */
export async function getAdminScopes(
  lang: string,
  options?: ApiOptions,
): Promise<AdminScopes> {
  return adminFetch(`/api/v1/admin/scholarship/scopes/?lang=${encodeURIComponent(lang)}`, options)
}

// ── Reviewers (Organisation → Reviewers, request #10, 2026-08-02) ─────────────

/**
 * One row of the reviewers table.
 *
 * Every figure is org-fenced and computed server-side; nothing here is re-derived on the client.
 * There is deliberately **no `programmes`** field (with one programme the column could only ever
 * say one thing) and **no corrections count** — reopens live on the detail page, with their
 * reasons, because a bare number beside a volunteer's name reads as a competence score.
 */
export interface AdminReviewer {
  id: number
  name: string
  email: string
  role: string
  /** Fluency codes the reviewer can actually interview in — 'conversational' or better. */
  languages: string[]
  open_now: number
  completed: number
  /** MEDIAN days from assignment to verdict. `null` = no completed review, NOT zero. */
  turnaround_days: number | null
  /** Stepped back from NEW work. Never a revoke — see `PartnerAdmin.paused_at`. */
  paused: boolean
  paused_at: string | null
}

/** One reopened decision, with the reason recorded at the time it was reopened. */
export interface AdminReviewerReopen {
  id: number
  application_id: number
  reason: string
  reopened_by: string
  at: string
}

/**
 * One reviewer, whole.
 *
 * The contact block is a deliberate, PARTIAL widening of a self-scoped profile: phone yes, **home
 * address never** — it is not serialised at all, and a backend test asserts it cannot appear.
 * See `docs/scholarship/role-matrix.md`.
 */
export interface AdminReviewerDetail extends AdminReviewer {
  /** Verdicts on cases assigned to them that SOMEBODY ELSE recorded — not on their record. */
  decided_by_other: number
  progressed: number
  declined: number
  created_at: string
  qualification: string
  university: string
  graduation_year: number | null
  field_of_study: string
  phone: string
  share_phone_with_students: boolean
  reopens: AdminReviewerReopen[]
}

export async function listReviewers(options?: ApiOptions): Promise<{ reviewers: AdminReviewer[] }> {
  return adminFetch('/api/v1/admin/reviewers/', options)
}

export async function getReviewerDetail(
  id: number, options?: ApiOptions,
): Promise<AdminReviewerDetail> {
  return adminFetch(`/api/v1/admin/reviewers/${id}/`, options)
}
