import {
  countAGrades,
  profileToApplyDefaults,
  profileAcademicSummary,
  buildApplicationPayload,
  applyFormError,
  nricChanged,
  fundingTotal,
  emptyDetailsForm,
  applicationToDetailsForm,
  buildDetailsPayload,
  DOC_TYPES,
  formatFileSize,
  REFERRING_ORG_OPTIONS,
  CALL_LANGUAGE_OPTIONS,
  MALAYSIAN_STATES,
  stashApplyForm,
  popApplyStash,
  hasApplyReturn,
  clearApplyReturn,
  APPLY_STASH_KEY,
  APPLY_RETURN_KEY,
  type ApplyFormState,
} from '@/lib/scholarship'
import type { StudentProfile, ScholarshipApplication } from '@/lib/api'

function baseForm(over: Partial<ApplyFormState> = {}): ApplyFormState {
  return {
    // About Me — all required
    name: 'Priya',
    school: 'SMK Taman Desa',
    nric: '080101-14-1234',
    referringOrg: 'cumig',
    homeState: 'Selangor',
    phone: '012-345 6789',
    // My Family
    householdIncome: '2500',
    householdSize: '5',
    receivesStr: true,
    receivesJkm: false,
    parentName: '',
    parentPhone: '',
    callLanguage: '',
    // My Plans / My Support (unchanged this sprint)
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
  it('pre-fills About Me + My Family from the profile (academic is read-only, not in the form)', () => {
    const profile = {
      grades: { math: 'A', sej: 'A', tamil: 'A+', eko: 'A-', sci: 'A-' },
      exam_type: 'spm',
      name: 'Priya Devi', school: 'SMK Taman Desa', nric: '080101-14-1234',
      referral_source: 'cumig', preferred_state: 'Selangor', contact_phone: '012-345 6789',
      preferred_call_language: 'ta',
      guardians: [{ name: 'Rajan', phone: '011-2222 3333' }],
      household_income: 2500, household_size: 6, receives_str: true, receives_jkm: false,
    } as unknown as StudentProfile
    const d = profileToApplyDefaults(profile)
    // About Me
    expect(d.name).toBe('Priya Devi')
    expect(d.school).toBe('SMK Taman Desa')
    expect(d.nric).toBe('080101-14-1234')
    expect(d.referringOrg).toBe('cumig')
    expect(d.homeState).toBe('Selangor')
    expect(d.phone).toBe('012-345 6789')
    // My Family
    expect(d.householdIncome).toBe('2500')
    expect(d.householdSize).toBe('6')
    expect(d.receivesStr).toBe(true)
    expect(d.parentName).toBe('Rajan')
    expect(d.parentPhone).toBe('011-2222 3333')
    expect(d.callLanguage).toBe('ta')
    // not pre-checked / read from profile
    expect(d.consentToContact).toBe(false)
    expect(d.intendsTertiary2026).toBe(true)
    expect((d as Record<string, unknown>).spmACount).toBeUndefined()
  })
  it('handles a null profile (blank editable fields)', () => {
    const d = profileToApplyDefaults(null)
    expect(d.name).toBe('')
    expect(d.nric).toBe('')
    expect(d.referringOrg).toBe('')
    expect(d.parentName).toBe('')
    expect(d.householdIncome).toBe('')
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
  it('maps About Me + My Family + application fields to a snake_case payload (no academic, no NRIC)', () => {
    const p = buildApplicationPayload(baseForm({ parentName: 'Rajan', parentPhone: '011-2222 3333' })) as Record<string, unknown>
    expect(p.name).toBe('Priya')
    expect(p.school).toBe('SMK Taman Desa')
    expect(p.preferred_state).toBe('Selangor')
    expect(p.contact_phone).toBe('012-345 6789')
    expect(p.referral_source).toBe('cumig')
    expect(p.guardians).toEqual([{ name: 'Rajan', phone: '011-2222 3333' }])
    expect(p.household_income).toBe(2500)
    expect(p.household_size).toBe(5)
    expect(p.receives_str).toBe(true)
    expect(p.intended_pathway).toBe('asasi')
    expect(p.consent_to_contact).toBe(true)
    expect(p.form_data).toEqual({})
    // academic data + NRIC are never posted here (profile / claim path)
    expect(p.spm_a_count).toBeUndefined()
    expect(p.nric).toBeUndefined()
  })
  it('trims text and omits guardians when parent fields are blank', () => {
    const p = buildApplicationPayload(baseForm({ name: '  Priya  ', parentName: '', parentPhone: '' }))
    expect(p.name).toBe('Priya')
    expect(p.guardians).toEqual([])
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
  it('flags missing About Me fields in tab order', () => {
    expect(applyFormError(baseForm({ name: '  ' }))).toBe('name')
    expect(applyFormError(baseForm({ school: '' }))).toBe('school')
    expect(applyFormError(baseForm({ nric: '123' }))).toBe('nric')        // bad format
    expect(applyFormError(baseForm({ nric: '' }))).toBe('nric')
    expect(applyFormError(baseForm({ referringOrg: '' }))).toBe('org')
    expect(applyFormError(baseForm({ homeState: '' }))).toBe('state')
    expect(applyFormError(baseForm({ phone: '' }))).toBe('phone')
  })
  it('requires household income', () => {
    expect(applyFormError(baseForm({ householdIncome: '' }))).toBe('income')
  })
  it('requires consent', () => {
    expect(applyFormError(baseForm({ consentToContact: false }))).toBe('consent')
  })
  it('surfaces the earliest-tab problem first', () => {
    // both name and consent are wrong → About Me wins (earlier tab)
    expect(applyFormError(baseForm({ name: '', consentToContact: false }))).toBe('name')
  })
})

describe('nricChanged', () => {
  it('is false when the form NRIC matches the profile', () => {
    expect(nricChanged(baseForm({ nric: '080101-14-1234' }), { nric: '080101-14-1234' } as unknown as StudentProfile)).toBe(false)
  })
  it('is true when the form NRIC differs (or profile has none)', () => {
    expect(nricChanged(baseForm({ nric: '080101-14-9999' }), { nric: '080101-14-1234' } as unknown as StudentProfile)).toBe(true)
    expect(nricChanged(baseForm({ nric: '080101-14-1234' }), null)).toBe(true)
  })
})

describe('apply stash / return marker (My Results onboarding round-trip)', () => {
  function fakeStorage() {
    const m = new Map<string, string>()
    return {
      getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
      setItem: (k: string, v: string) => { m.set(k, v) },
      removeItem: (k: string) => { m.delete(k) },
      _map: m,
    }
  }

  it('stashes the form and sets the return marker', () => {
    const s = fakeStorage()
    const form = baseForm({ name: 'Priya', householdIncome: '1800' })
    stashApplyForm(form, s)
    expect(s.getItem(APPLY_RETURN_KEY)).toBe('1')
    expect(hasApplyReturn(s)).toBe(true)
    expect(JSON.parse(s.getItem(APPLY_STASH_KEY)!).name).toBe('Priya')
  })

  it('pops and consumes the stash (round-trips the form, then clears it)', () => {
    const s = fakeStorage()
    const form = baseForm({ school: 'SMK Taman Desa', parentName: 'Rajan' })
    stashApplyForm(form, s)
    const restored = popApplyStash(s)
    expect(restored?.school).toBe('SMK Taman Desa')
    expect(restored?.parentName).toBe('Rajan')
    // consumed — a second pop returns null
    expect(popApplyStash(s)).toBeNull()
  })

  it('returns null on missing / unparseable stash', () => {
    const s = fakeStorage()
    expect(popApplyStash(s)).toBeNull()
    s.setItem(APPLY_STASH_KEY, '{not json')
    expect(popApplyStash(s)).toBeNull()
  })

  it('clears the return marker', () => {
    const s = fakeStorage()
    stashApplyForm(baseForm(), s)
    clearApplyReturn(s)
    expect(hasApplyReturn(s)).toBe(false)
  })

  it('no-ops safely when no storage is available (SSR/node without injection)', () => {
    expect(() => stashApplyForm(baseForm())).not.toThrow()
    expect(popApplyStash()).toBeNull()
    expect(hasApplyReturn()).toBe(false)
    expect(() => clearApplyReturn()).not.toThrow()
  })
})

describe('option constants', () => {
  it('lists the legacy referring-org codes incl. cumig and other', () => {
    expect(REFERRING_ORG_OPTIONS).toContain('cumig')
    expect(REFERRING_ORG_OPTIONS).toContain('other')
    expect(REFERRING_ORG_OPTIONS.length).toBe(9)
  })
  it('offers the four call languages and the 16 states', () => {
    expect(CALL_LANGUAGE_OPTIONS).toEqual(['en', 'ms', 'ta', 'mixed'])
    expect(MALAYSIAN_STATES).toContain('Selangor')
    expect(MALAYSIAN_STATES.length).toBe(16)
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
