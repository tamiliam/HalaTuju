import {
  countAGrades,
  profileToApplyDefaults,
  buildApplicationPayload,
  applyFormError,
  fundingTotal,
  emptyDetailsForm,
  applicationToDetailsForm,
  buildDetailsPayload,
  type ApplyFormState,
} from '@/lib/scholarship'
import type { StudentProfile, ScholarshipApplication } from '@/lib/api'

function baseForm(over: Partial<ApplyFormState> = {}): ApplyFormState {
  return {
    qualification: 'spm',
    spmACount: '5',
    stpmPngk: '',
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
  it('defaults to SPM with a snapshotted A-count', () => {
    const profile = {
      grades: { math: 'A', sej: 'A', tamil: 'A+', eko: 'A-', sci: 'A-' },
      exam_type: 'spm',
    } as unknown as StudentProfile
    const d = profileToApplyDefaults(profile)
    expect(d.qualification).toBe('spm')
    expect(d.spmACount).toBe('5')
    expect(d.consentToContact).toBe(false)
    expect(d.intendsTertiary2026).toBe(true)
  })
  it('uses STPM PNGK when exam_type is stpm', () => {
    const profile = { exam_type: 'stpm', stpm_cgpa: 3.5 } as unknown as StudentProfile
    const d = profileToApplyDefaults(profile)
    expect(d.qualification).toBe('stpm')
    expect(d.stpmPngk).toBe('3.5')
  })
  it('handles a null profile', () => {
    const d = profileToApplyDefaults(null)
    expect(d.qualification).toBe('spm')
    expect(d.spmACount).toBe('')
  })
})

describe('buildApplicationPayload', () => {
  it('maps SPM form to snake_case payload, nulling STPM fields', () => {
    const p = buildApplicationPayload(baseForm())
    expect(p.qualification).toBe('spm')
    expect(p.spm_a_count).toBe(5)
    expect(p.stpm_pngk).toBeNull()
    expect(p.household_income).toBe(2500)
    expect(p.household_size).toBe(5)
    expect(p.receives_str).toBe(true)
    expect(p.consent_to_contact).toBe(true)
    expect(p.form_data).toEqual({})
  })
  it('maps STPM form, nulling SPM A-count', () => {
    const p = buildApplicationPayload(baseForm({ qualification: 'stpm', stpmPngk: '3.2', spmACount: '' }))
    expect(p.spm_a_count).toBeNull()
    expect(p.stpm_pngk).toBeCloseTo(3.2)
  })
  it('puts notes into form_data', () => {
    const p = buildApplicationPayload(baseForm({ notes: '  hello  ' }))
    expect(p.form_data).toEqual({ notes: 'hello' })
  })
})

describe('applyFormError', () => {
  it('passes a complete SPM form', () => {
    expect(applyFormError(baseForm())).toBeNull()
  })
  it('requires consent', () => {
    expect(applyFormError(baseForm({ consentToContact: false }))).toBe('consent')
  })
  it('requires an A-count for SPM', () => {
    expect(applyFormError(baseForm({ spmACount: '' }))).toBe('aCount')
  })
  it('requires a PNGK for STPM', () => {
    expect(applyFormError(baseForm({ qualification: 'stpm', stpmPngk: '', spmACount: '' }))).toBe('pngk')
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
