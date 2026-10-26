/**
 * Third results route S2b — the two pure helpers the apply form and /profile read for a
 * Matriculation / Asasi / Diploma holder: `profileAcademicSummary` (which results, whether there is
 * data, the SERVER's overall CGPA) and `applyFormError` (a tertiary student names a degree, with no
 * SPM pathway step). A missed branch here silently read the route as SPM (roadmap risk list).
 */
import { applyFormError, profileAcademicSummary, profileToApplyDefaults } from '@/lib/scholarship'
import type { ApplyFormState } from '@/lib/scholarship'
import type { StudentProfile } from '@/lib/api'

const p = (x: Record<string, unknown>) => x as unknown as StudentProfile

describe('profileAcademicSummary on the third route', () => {
  it.each(['matric', 'asasi', 'diploma'])('reads a served %s as itself, with the served overall CGPA', (kind) => {
    const s = profileAcademicSummary(p({ results_held: kind, higher_cgpa: 3.5, overall_cgpa: 3.47, grades: {} }))
    expect(s.examType).toBe(kind)
    expect(s.hasData).toBe(true)
    expect(s.overallCgpa).toBe(3.47)
  })

  it('has no data without a CGPA — never an SPM summary of an empty grade list', () => {
    const s = profileAcademicSummary(p({ results_held: 'asasi', higher_cgpa: null, grades: {} }))
    expect(s.examType).toBe('asasi')
    expect(s.hasData).toBe(false)
  })

  it('falls back to the declaration for an older payload, as SPM and STPM do', () => {
    expect(profileAcademicSummary(p({ exam_type: 'diploma', higher_cgpa: 2.8 })).examType).toBe('diploma')
  })

  it('leaves SPM and STPM as they were, the STPM overall CGPA being its stored one', () => {
    expect(profileAcademicSummary(p({ results_held: 'spm', grades: { bm: 'A' } })).examType).toBe('spm')
    const stpm = profileAcademicSummary(p({ results_held: 'stpm', stpm_cgpa: 3.7 }))
    expect([stpm.examType, stpm.overallCgpa, stpm.hasData]).toEqual(['stpm', 3.7, true])
    expect(profileAcademicSummary(p({ results_held: 'phd' })).examType).toBe('spm')
  })
})

describe('applyFormError on the third route', () => {
  const decided = (over: Partial<ApplyFormState>) => ({
    ...profileToApplyDefaults(null), name: 'Priya', school: 'SMK X', nric: '080101-14-1234', referringOrg: 'cumig',
    homeState: 'Selangor', phone: '012-345 6789', householdIncome: '2500', householdSize: '5',
    consentToContact: true, declarationName: 'Priya', pathwayCertainty: 'sure', ...over,
  } as ApplyFormState)

  it.each(['matric', 'asasi', 'diploma'] as const)('%s: a decided student must name a degree, not a pathway', (kind) => {
    expect(applyFormError(decided({ chosenPathway: '', chosenProgramme: null }), kind)).toBe('chosenProgramme')
    expect(applyFormError(decided({
      chosenPathway: '', chosenProgramme: { courseId: 'UM1', courseName: 'Bachelor', fieldKey: '' },
    }), kind)).toBeNull()
  })

  it('an SPM leaver still needs the pathway first (positive control)', () => {
    expect(applyFormError(decided({ chosenPathway: '', chosenProgramme: null }), 'spm')).toBe('chosenPathway')
  })
})
