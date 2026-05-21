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

export interface ApplyFormState {
  qualification: Qualification
  spmACount: string   // strings for controlled inputs
  stpmPngk: string
  householdIncome: string
  householdSize: string
  receivesStr: boolean
  receivesJkm: boolean
  intendedPathway: IntendedPathway
  intendsTertiary2026: boolean
  consentToContact: boolean
  notes: string
}

export function profileToApplyDefaults(profile?: StudentProfile | null): ApplyFormState {
  const qualification: Qualification = profile?.exam_type === 'stpm' ? 'stpm' : 'spm'
  const aCount = countAGrades(profile?.grades)
  return {
    qualification,
    spmACount: aCount > 0 ? String(aCount) : '',
    stpmPngk: profile?.stpm_cgpa != null ? String(profile.stpm_cgpa) : '',
    householdIncome: '',
    householdSize: '',
    receivesStr: false,
    receivesJkm: false,
    intendedPathway: '',
    intendsTertiary2026: true,
    consentToContact: false,
    notes: '',
  }
}

export interface ApplicationPayload {
  qualification: Qualification
  spm_a_count: number | null
  stpm_pngk: number | null
  household_income: number | null
  household_size: number | null
  receives_str: boolean
  receives_jkm: boolean
  intended_pathway: string
  intends_tertiary_2026: boolean
  consent_to_contact: boolean
  form_data: Record<string, unknown>
}

function toIntOrNull(s: string): number | null {
  const t = s.trim()
  if (t === '') return null
  const n = parseInt(t, 10)
  return Number.isFinite(n) ? n : null
}

function toFloatOrNull(s: string): number | null {
  const t = s.trim()
  if (t === '') return null
  const n = parseFloat(t)
  return Number.isFinite(n) ? n : null
}

export function buildApplicationPayload(form: ApplyFormState): ApplicationPayload {
  const isSpm = form.qualification === 'spm'
  return {
    qualification: form.qualification,
    spm_a_count: isSpm ? toIntOrNull(form.spmACount) : null,
    stpm_pngk: isSpm ? null : toFloatOrNull(form.stpmPngk),
    household_income: toIntOrNull(form.householdIncome),
    household_size: toIntOrNull(form.householdSize),
    receives_str: form.receivesStr,
    receives_jkm: form.receivesJkm,
    intended_pathway: form.intendedPathway,
    intends_tertiary_2026: form.intendsTertiary2026,
    consent_to_contact: form.consentToContact,
    form_data: form.notes.trim() ? { notes: form.notes.trim() } : {},
  }
}

/**
 * Returns the i18n error sub-key for the first validation problem, or null if
 * the form is ready to submit. Mirrors the backend's hard requirements.
 */
export function applyFormError(form: ApplyFormState): string | null {
  if (!form.consentToContact) return 'consent'
  if (form.qualification === 'spm' && toIntOrNull(form.spmACount) === null) return 'aCount'
  if (form.qualification === 'stpm' && toFloatOrNull(form.stpmPngk) === null) return 'pngk'
  if (toIntOrNull(form.householdIncome) === null) return 'income'
  return null
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
