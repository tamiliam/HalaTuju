import {
  countAGrades,
  profileToApplyDefaults,
  profileAcademicSummary,
  buildApplicationPayload,
  applyFormError,
  fundingTotal,
  emptyDetailsForm,
  applicationToDetailsForm,
  buildDetailsPayload,
  DOC_TYPES,
  formatFileSize,
  type ApplyFormState,
} from '@/lib/scholarship'
import type { StudentProfile, ScholarshipApplication } from '@/lib/api'

function baseForm(over: Partial<ApplyFormState> = {}): ApplyFormState {
  return {
    householdIncome: '2500',
    householdSize: '5',
    receivesStr: true,
    receivesJkm: false,
    intendedPathway: 'asasi',
    intendsTertiary2026: true,
    consentToContact: true,
    notes: '',
    ...over,
  }
}

describe('countAGrades', () => {
  it('counts A+, A and A- (case/space tolerant)', () => {
    expect(countAGrades({ a: 'A+', b: 'A', c: 'A-', d: 'B+', e: 'C' })).toBe(3)
    expect(countAGrades({ a: ' a+ ', b: 'a-' })).toBe(2)
  })
  it('handles empty/undefined', () => {
    expect(countAGrades({})).toBe(0)
    expect(countAGrades(null)).toBe(0)
    expect(countAGrades(undefined)).toBe(0)
  })
})

describe('profileToApplyDefaults', () => {
  it('pre-fills the financial fields from the profile (academic is read-only, not in the form)', () => {
    const profile = {
      grades: { math: 'A', sej: 'A', tamil: 'A+', eko: 'A-', sci: 'A-' },
      exam_type: 'spm',
      household_income: 2500, household_size: 6, receives_str: true, receives_jkm: false,
    } as unknown as StudentProfile
    const d = profileToApplyDefaults(profile)
    expect(d.householdIncome).toBe('2500')
    expect(d.householdSize).toBe('6')
    expect(d.receivesStr).toBe(true)
    expect(d.consentToContact).toBe(false)
    expect(d.intendsTertiary2026).toBe(true)
    // academic fields are NOT part of the form state any more
    expect((d as Record<string, unknown>).spmACount).toBeUndefined()
  })
  it('handles a null profile (blank financial fields)', () => {
    const d = profileToApplyDefaults(null)
    expect(d.householdIncome).toBe('')
    expect(d.householdSize).toBe('')
    expect(d.receivesStr).toBe(false)
  })
})

describe('profileAcademicSummary', () => {
  it('summarises SPM A/A+ counts from grades', () => {
    const profile = { exam_type: 'spm', grades: { a: 'A+', b: 'A+', c: 'A', d: 'A-', e: 'B' } } as unknown as StudentProfile
    const s = profileAcademicSummary(profile)
    expect(s.examType).toBe('spm')
    expect(s.aCount).toBe(4)
    expect(s.aPlusCount).toBe(2)
    expect(s.hasData).toBe(true)
  })
  it('uses STPM CGPA when exam_type is stpm', () => {
    const s = profileAcademicSummary({ exam_type: 'stpm', stpm_cgpa: 3.5 } as unknown as StudentProfile)
    expect(s.examType).toBe('stpm')
    expect(s.stpmCgpa).toBe(3.5)
    expect(s.hasData).toBe(true)
  })
  it('flags missing academic data', () => {
    expect(profileAcademicSummary(null).hasData).toBe(false)
    expect(profileAcademicSummary({ exam_type: 'spm', grades: {} } as unknown as StudentProfile).hasData).toBe(false)
    expect(profileAcademicSummary({ exam_type: 'stpm' } as unknown as StudentProfile).hasData).toBe(false)
  })
})

describe('buildApplicationPayload', () => {
  it('maps the financial + application fields to a snake_case payload (no academic fields)', () => {
    const p = buildApplicationPayload(baseForm()) as Record<string, unknown>
    expect(p.household_income).toBe(2500)
    expect(p.household_size).toBe(5)
    expect(p.receives_str).toBe(true)
    expect(p.intended_pathway).toBe('asasi')
    expect(p.consent_to_contact).toBe(true)
    expect(p.form_data).toEqual({})
    // academic data is read from the profile server-side, never posted
    expect(p.qualification).toBeUndefined()
    expect(p.spm_a_count).toBeUndefined()
    expect(p.stpm_pngk).toBeUndefined()
  })
  it('nulls a blank income / size', () => {
    const p = buildApplicationPayload(baseForm({ householdIncome: '', householdSize: '' }))
    expect(p.household_income).toBeNull()
    expect(p.household_size).toBeNull()
  })
  it('puts notes into form_data', () => {
    const p = buildApplicationPayload(baseForm({ notes: '  hello  ' }))
    expect(p.form_data).toEqual({ notes: 'hello' })
  })
})

describe('applyFormError', () => {
  it('passes a complete form', () => {
    expect(applyFormError(baseForm())).toBeNull()
  })
  it('requires consent', () => {
    expect(applyFormError(baseForm({ consentToContact: false }))).toBe('consent')
  })
  it('requires household income', () => {
    expect(applyFormError(baseForm({ householdIncome: '' }))).toBe('income')
  })
})

describe('fundingTotal', () => {
  it('sums line items plus allowance × months', () => {
    const f = { ...emptyDetailsForm(), laptop: '2000', books: '500', monthlyAllowance: '300', allowanceMonths: '10', other: '200' }
    expect(fundingTotal(f)).toBe(2000 + 500 + 3000 + 200)
  })
  it('treats blanks as zero', () => {
    expect(fundingTotal(emptyDetailsForm())).toBe(0)
  })
})

describe('buildDetailsPayload', () => {
  it('maps form to snake_case with nested funding_need (trimmed)', () => {
    const f = { ...emptyDetailsForm(), aspirations: '  be a teacher ', laptop: '2000', allowanceMonths: '10', monthlyAllowance: '300' }
    const p = buildDetailsPayload(f) as { aspirations: string; funding_need: Record<string, number> }
    expect(p.aspirations).toBe('be a teacher')
    expect(p.funding_need.laptop).toBe(2000)
    expect(p.funding_need.monthly_allowance).toBe(300)
    expect(p.funding_need.allowance_months).toBe(10)
  })
})

describe('applicationToDetailsForm', () => {
  it('pre-fills from an application with a funding need (zeros blanked)', () => {
    const app = {
      aspirations: 'Teach', plans: '', fears: '', justification: 'Need help',
      funding_need: {
        tuition_gap: 0, laptop: 2000, hostel: 0, transport: 0, books: 0,
        monthly_allowance: 300, allowance_months: 10, other: 0, other_desc: '', total: 5000,
      },
    } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.aspirations).toBe('Teach')
    expect(f.justification).toBe('Need help')
    expect(f.laptop).toBe('2000')
    expect(f.tuitionGap).toBe('')
    expect(f.monthlyAllowance).toBe('300')
  })
  it('handles a null funding need', () => {
    const app = { aspirations: '', plans: '', fears: '', justification: '', funding_need: null } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.laptop).toBe('')
    expect(f.aspirations).toBe('')
  })
})

describe('formatFileSize', () => {
  it('formats KB and MB', () => {
    expect(formatFileSize(0)).toBe('0 KB')
    expect(formatFileSize(500)).toBe('1 KB')
    expect(formatFileSize(2048)).toBe('2 KB')
    expect(formatFileSize(2 * 1024 * 1024)).toBe('2.0 MB')
  })
})

describe('DOC_TYPES', () => {
  it('lists the seven supporting document types', () => {
    expect(DOC_TYPES).toHaveLength(7)
    expect(DOC_TYPES).toContain('ic')
    expect(DOC_TYPES).toContain('reference_letter')
  })
})
