/**
 * B40 Assistance Programme — pure form helpers.
 *
 * Logic lives here (node-testable) so the page component stays a thin renderer.
 */
import type { StudentProfile, ScholarshipApplication } from '@/lib/api'

// SPM grades that count as an "A" for the shortlist (A+, A and A- all count,
// matching the backend's count_spm_a_grades and the B40 candidate profiles).
export const A_GRADES = new Set(['A+', 'A', 'A-'])

export function countAGrades(grades?: Record<string, string> | null): number {
  if (!grades) return 0
  return Object.values(grades).filter(
    (g) => typeof g === 'string' && A_GRADES.has(g.trim().toUpperCase())
  ).length
}

export type Qualification = 'spm' | 'stpm'
export type IntendedPathway =
  | '' | 'asasi' | 'matrik' | 'stpm' | 'pismp' | 'diploma' | 'degree' | 'other'

export const PATHWAY_OPTIONS: IntendedPathway[] = [
  'asasi', 'matrik', 'stpm', 'pismp', 'diploma', 'degree', 'other',
]

// Referring-organisation codes (fixed list from the legacy Google Form). Labels
// come from i18n (`scholarship.apply.org.<code>`). A code that matches an active
// PartnerOrganisation row links the FK server-side; the rest are generic sources.
export const REFERRING_ORG_OPTIONS = [
  'smc', 'cumig', 'pushparani', 'sathya_sai', 'halatuju', 'tara', 'govind', 'social', 'other',
] as const
export type ReferringOrg = typeof REFERRING_ORG_OPTIONS[number] | ''

// Preferred language for phone calls (B40 outreach). Labels via i18n
// (`scholarship.apply.callLang.<code>`); stored on profile.preferred_call_language.
export const CALL_LANGUAGE_OPTIONS = ['en', 'ms', 'ta', 'mixed'] as const
export type CallLanguage = typeof CALL_LANGUAGE_OPTIONS[number] | ''

// Mirrors the onboarding state list (onboarding/profile/page.tsx). Static — a
// fixed set of Malaysian states/federal territories that does not change.
export const MALAYSIAN_STATES = [
  'Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan',
  'Pahang', 'Perak', 'Perlis', 'Pulau Pinang', 'Sabah',
  'Sarawak', 'Selangor', 'Terengganu',
  'Kuala Lumpur', 'Labuan', 'Putrajaya',
] as const

// NRIC format XXXXXX-XX-XXXX (the claim endpoint does the full age/state checks).
const NRIC_RE = /^\d{6}-\d{2}-\d{4}$/

/**
 * Format raw NRIC keystrokes/paste into the canonical XXXXXX-XX-XXXX mask:
 * keep digits only, cap at 12, and insert dashes after the 6th and 8th digit.
 * Idempotent — re-running on an already-masked value returns it unchanged — so it
 * can be applied on every onChange. The output is exactly what NRIC_RE expects.
 */
export function formatNric(raw: string): string {
  const d = raw.replace(/\D/g, '').slice(0, 12)
  return [d.slice(0, 6), d.slice(6, 8), d.slice(8, 12)].filter(Boolean).join('-')
}

/**
 * Format raw phone keystrokes/paste into a readable Malaysian style: digits only,
 * capped at 11, grouped as `0XX-XXX XXXX` (or `0XX-XXXX XXXX` for 11 digits — the
 * last group is always the final 4). Idempotent, so safe to run on every onChange.
 */
export function formatPhone(raw: string): string {
  const d = raw.replace(/\D/g, '').slice(0, 11)
  if (d.length <= 3) return d
  const rest = d.slice(3)
  if (rest.length <= 4) return `${d.slice(0, 3)}-${rest}`
  return `${d.slice(0, 3)}-${rest.slice(0, rest.length - 4)} ${rest.slice(rest.length - 4)}`
}

// A Malaysian phone number is 9–11 digits starting with 0 (mobile 01X… or a
// landline 0X…). We validate on the digits, ignoring the display dashes/spaces.
export function isValidPhone(s: string): boolean {
  return /^0\d{8,10}$/.test(s.replace(/\D/g, ''))
}

// ── My Plans + My Support (Sprint 10) ────────────────────────────────────
// UPU / destination intent. 'ipts' (IPTS-only) is the engine's disqualifier;
// the form never blocks on it — the backend declines silently (S8 gate).
export type UpuStatus = '' | 'applied' | 'public_other' | 'ipts' | 'unknown'
export const UPU_OPTIONS: Exclude<UpuStatus, ''>[] = ['applied', 'public_other', 'ipts', 'unknown']

// Optional support questions (Yes / No / Not sure).
export type HelpChoice = '' | 'yes' | 'no' | 'unsure'
export const HELP_OPTIONS: Exclude<HelpChoice, ''>[] = ['yes', 'no', 'unsure']

// Other scholarships applied/held → funding-overlap signal (labels via i18n).
export const OTHER_SCHOLARSHIP_OPTIONS = ['jpa', 'petronas', 'mara', 'yayasan', 'bank_foundation', 'other'] as const

// A ranked course choice (rank derived from array order). Sourced from the
// student's saved courses; shape mirrors the backend `top_choices` entries.
export interface TopChoice {
  courseId: string
  courseName: string
  institution: string
}

/**
 * The apply form only carries fields the applicant edits here. Academic data
 * (exam type, grades, STPM CGPA) is read live from the canonical HalaTuju
 * profile — never collected or posted by this form. The financial fields below
 * are written back to the profile on submit (their canonical home).
 */
export interface ApplyFormState {
  // About Me (inline-editable; pre-filled from the profile, committed on submit).
  // NRIC is edited here but saved via the validated claim path, not the payload.
  name: string
  school: string
  nric: string
  referringOrg: ReferringOrg
  homeState: string
  phone: string
  // My Family
  householdIncome: string   // strings for controlled inputs
  householdSize: string
  receivesStr: boolean
  receivesJkm: boolean
  parentName: string
  parentPhone: string
  callLanguage: CallLanguage
  // My Plans
  pathwaysConsidered: string[]      // pathway keys (non-exclusive)
  topChoices: TopChoice[]           // ranked top-3 (from saved courses)
  upuStatus: UpuStatus
  fieldOfStudy: string              // field-taxonomy key
  otherScholarships: string[]       // scholarship keys
  otherScholarshipsText: string
  intendsTertiary2026: boolean      // engine hard gate — must be true to qualify
  // My Support
  helpUniversity: HelpChoice
  helpScholarship: HelpChoice
  anythingElse: string
  consentToContact: boolean
}

export function profileToApplyDefaults(profile?: StudentProfile | null): ApplyFormState {
  // Pre-fill every editable field from the canonical profile. The form holds the
  // edits in state and writes them back only on a successful submit. Academic
  // data (results) is shown read-only by My Results, not carried in this form.
  const guardian = profile?.guardians?.[0]
  return {
    name: profile?.name ?? '',
    school: profile?.school ?? '',
    // Pre-filled values are masked too, so an older unformatted profile value
    // still displays as XXXXXX-XX-XXXX / 0XX-XXX XXXX.
    nric: formatNric(profile?.nric ?? ''),
    referringOrg: (profile?.referral_source as ReferringOrg) ?? '',
    homeState: profile?.preferred_state ?? '',
    phone: formatPhone(profile?.contact_phone ?? ''),
    householdIncome: profile?.household_income != null ? String(profile.household_income) : '',
    householdSize: profile?.household_size != null ? String(profile.household_size) : '',
    receivesStr: !!profile?.receives_str,
    receivesJkm: !!profile?.receives_jkm,
    parentName: guardian?.name ?? '',
    parentPhone: formatPhone(guardian?.phone ?? ''),
    callLanguage: (profile?.preferred_call_language as CallLanguage) ?? '',
    pathwaysConsidered: [],
    topChoices: [],
    upuStatus: '',
    fieldOfStudy: '',
    otherScholarships: [],
    otherScholarshipsText: '',
    intendsTertiary2026: true,
    helpUniversity: '',
    helpScholarship: '',
    anythingElse: '',
    consentToContact: false,
  }
}

/** A read-only summary of the profile's academic standing, for display only. */
export interface AcademicSummary {
  examType: Qualification
  aCount: number          // SPM A+/A/A- count
  aPlusCount: number      // SPM A+ count, for the "including N A+" line
  stpmCgpa: number | null
  hasData: boolean        // does the profile carry enough academic data to score?
}

export function profileAcademicSummary(profile?: StudentProfile | null): AcademicSummary {
  const examType: Qualification = profile?.exam_type === 'stpm' ? 'stpm' : 'spm'
  const grades = profile?.grades
  const aCount = countAGrades(grades)
  const aPlusCount = grades
    ? Object.values(grades).filter((g) => typeof g === 'string' && g.trim().toUpperCase() === 'A+').length
    : 0
  const stpmCgpa = profile?.stpm_cgpa ?? null
  const hasData = examType === 'stpm'
    ? stpmCgpa != null
    : !!grades && Object.keys(grades).length > 0
  return { examType, aCount, aPlusCount, stpmCgpa, hasData }
}

export interface ApplicationPayload {
  // About Me + My Family profile fields (write-only; synced to the profile
  // server-side). NRIC is NOT here — it goes through the claim path on submit.
  name: string
  school: string
  preferred_state: string
  contact_phone: string
  preferred_call_language: string
  referral_source: string
  guardians: { name: string; phone: string }[]
  household_income: number | null
  household_size: number | null
  receives_str: boolean
  receives_jkm: boolean
  intends_tertiary_2026: boolean
  consent_to_contact: boolean
  // My Plans + My Support (Sprint 10)
  pathways_considered: string[]
  top_choices: { rank: number; course_id: string; course_name: string; institution: string }[]
  upu_status: string
  field_of_study: string
  other_scholarships: string[]
  other_scholarships_text: string
  help_university: string
  help_scholarship: string
  anything_else: string
  form_data: Record<string, unknown>
}

function toIntOrNull(s: string): number | null {
  const t = s.trim()
  if (t === '') return null
  const n = parseInt(t, 10)
  return Number.isFinite(n) ? n : null
}

export function buildApplicationPayload(form: ApplyFormState): ApplicationPayload {
  // Academic fields are intentionally absent — the backend reads them from the
  // profile. The About Me + My Family fields are synced to the profile
  // server-side. NRIC is committed separately via the validated claim path.
  const guardians = form.parentName.trim() || form.parentPhone.trim()
    ? [{ name: form.parentName.trim(), phone: form.parentPhone.trim() }]
    : []
  return {
    name: form.name.trim(),
    school: form.school.trim(),
    preferred_state: form.homeState,
    contact_phone: form.phone.trim(),
    preferred_call_language: form.callLanguage,
    referral_source: form.referringOrg,
    guardians,
    household_income: toIntOrNull(form.householdIncome),
    household_size: toIntOrNull(form.householdSize),
    receives_str: form.receivesStr,
    receives_jkm: form.receivesJkm,
    intends_tertiary_2026: form.intendsTertiary2026,
    consent_to_contact: form.consentToContact,
    // My Plans + My Support — rank is derived from the top-3 selection order.
    pathways_considered: form.pathwaysConsidered,
    top_choices: form.topChoices.map((c, i) => ({
      rank: i + 1, course_id: c.courseId, course_name: c.courseName, institution: c.institution,
    })),
    upu_status: form.upuStatus,
    field_of_study: form.fieldOfStudy,
    other_scholarships: form.otherScholarships,
    other_scholarships_text: form.otherScholarshipsText.trim(),
    help_university: form.helpUniversity,
    help_scholarship: form.helpScholarship,
    anything_else: form.anythingElse.trim(),
    form_data: {},
  }
}

/** True when the form's NRIC differs from what's on the profile (needs a claim call). */
export function nricChanged(form: ApplyFormState, profile?: StudentProfile | null): boolean {
  return form.nric.trim() !== (profile?.nric ?? '').trim()
}

/**
 * Returns the i18n error sub-key for the first validation problem, or null if the
 * form is ready to submit. Ordered by tab (About Me → My Family → consent) so the
 * earliest-section problem surfaces first. The full NRIC age/state checks and the
 * academic floor are enforced server-side (claim endpoint / profile), not here.
 */
export function applyFormError(form: ApplyFormState): string | null {
  // About Me — all required.
  if (!form.name.trim()) return 'name'
  if (!form.school.trim()) return 'school'
  if (!NRIC_RE.test(form.nric.trim())) return 'nric'
  if (!form.referringOrg) return 'org'
  if (!form.homeState) return 'state'
  if (!isValidPhone(form.phone)) return 'phone'
  // My Family — exact household income required (drives per-capita need).
  if (toIntOrNull(form.householdIncome) === null) return 'income'
  // Parent/guardian phone is optional, but if given it must be a valid number.
  if (form.parentPhone.trim() && !isValidPhone(form.parentPhone)) return 'parentPhone'
  // My Support — consent required to apply.
  if (!form.consentToContact) return 'consent'
  return null
}

// ── My Results → onboarding round-trip (Sprint 9b) ───────────────────────
// Editing/adding results sends the student through the full onboarding flow.
// The apply form only commits on submit, so before leaving we STASH the
// in-progress About Me / My Family edits and set a RETURN marker; the final
// onboarding step reads the marker to route back here (and we restore the stash).
// sessionStorage keys are constants (not string literals) to avoid drift.
export const APPLY_STASH_KEY = 'halatuju_apply_stash'
export const APPLY_RETURN_KEY = 'halatuju_apply_return'

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

/** sessionStorage if available (browser), else null (SSR / node tests without injection). */
function safeSession(): StorageLike | null {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null
  } catch {
    return null
  }
}

/** Stash the in-progress form and mark that onboarding should return to the apply page. */
export function stashApplyForm(form: ApplyFormState, storage?: StorageLike): void {
  const s = storage ?? safeSession()
  if (!s) return
  s.setItem(APPLY_STASH_KEY, JSON.stringify(form))
  s.setItem(APPLY_RETURN_KEY, '1')
}

/** Read and consume the stashed form (returns null if none / unparseable). */
export function popApplyStash(storage?: StorageLike): ApplyFormState | null {
  const s = storage ?? safeSession()
  if (!s) return null
  const raw = s.getItem(APPLY_STASH_KEY)
  if (!raw) return null
  s.removeItem(APPLY_STASH_KEY)
  try {
    return JSON.parse(raw) as ApplyFormState
  } catch {
    return null
  }
}

/** True when onboarding was entered from the apply form (should return to it). */
export function hasApplyReturn(storage?: StorageLike): boolean {
  const s = storage ?? safeSession()
  return !!s && s.getItem(APPLY_RETURN_KEY) === '1'
}

/** Clear the return marker (after routing back to the apply page). */
export function clearApplyReturn(storage?: StorageLike): void {
  const s = storage ?? safeSession()
  s?.removeItem(APPLY_RETURN_KEY)
}

// ── STEP 2: deeper-info + funding-need form (Sprint 4b) ──────────────────

export interface DetailsFormState {
  aspirations: string
  plans: string
  fears: string
  justification: string
  tuitionGap: string
  laptop: string
  hostel: string
  transport: string
  books: string
  monthlyAllowance: string
  allowanceMonths: string
  other: string
  otherDesc: string
}

function intOr0(s: string): number {
  const n = parseInt(s.trim(), 10)
  return Number.isFinite(n) ? n : 0
}

/** Live total: line items + monthly allowance × months. Mirrors the backend total. */
export function fundingTotal(f: DetailsFormState): number {
  return (
    intOr0(f.tuitionGap) + intOr0(f.laptop) + intOr0(f.hostel) + intOr0(f.transport)
    + intOr0(f.books) + intOr0(f.monthlyAllowance) * intOr0(f.allowanceMonths) + intOr0(f.other)
  )
}

export function emptyDetailsForm(): DetailsFormState {
  return {
    aspirations: '', plans: '', fears: '', justification: '',
    tuitionGap: '', laptop: '', hostel: '', transport: '', books: '',
    monthlyAllowance: '', allowanceMonths: '', other: '', otherDesc: '',
  }
}

export function applicationToDetailsForm(app: ScholarshipApplication): DetailsFormState {
  const fn = app.funding_need
  const numStr = (n: number | undefined) => (n != null && n !== 0 ? String(n) : '')
  return {
    aspirations: app.aspirations || '',
    plans: app.plans || '',
    fears: app.fears || '',
    justification: app.justification || '',
    tuitionGap: numStr(fn?.tuition_gap),
    laptop: numStr(fn?.laptop),
    hostel: numStr(fn?.hostel),
    transport: numStr(fn?.transport),
    books: numStr(fn?.books),
    monthlyAllowance: numStr(fn?.monthly_allowance),
    allowanceMonths: numStr(fn?.allowance_months),
    other: numStr(fn?.other),
    otherDesc: fn?.other_desc || '',
  }
}

export function buildDetailsPayload(f: DetailsFormState): Record<string, unknown> {
  return {
    aspirations: f.aspirations.trim(),
    plans: f.plans.trim(),
    fears: f.fears.trim(),
    justification: f.justification.trim(),
    funding_need: {
      tuition_gap: intOr0(f.tuitionGap),
      laptop: intOr0(f.laptop),
      hostel: intOr0(f.hostel),
      transport: intOr0(f.transport),
      books: intOr0(f.books),
      monthly_allowance: intOr0(f.monthlyAllowance),
      allowance_months: intOr0(f.allowanceMonths),
      other: intOr0(f.other),
      other_desc: f.otherDesc.trim(),
    },
  }
}

// ── Documents (Sprint 5b) ────────────────────────────────────────────────

export const DOC_TYPES = [
  'ic', 'results_slip', 'photo', 'epf', 'str', 'statement_of_intent', 'reference_letter',
] as const
export type DocType = typeof DOC_TYPES[number]

export function formatFileSize(bytes: number): string {
  if (!bytes || bytes < 0) return '0 KB'
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
