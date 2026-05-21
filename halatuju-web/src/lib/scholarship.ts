/**
 * B40 Assistance Programme — pure form helpers.
 *
 * Logic lives here (node-testable) so the page component stays a thin renderer.
 */
import type { StudentProfile } from '@/lib/api'

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
