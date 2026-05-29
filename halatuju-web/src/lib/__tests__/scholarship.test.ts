import {
  countAGrades,
  profileToApplyDefaults,
  profileAcademicSummary,
  buildApplicationPayload,
  applyFormError,
  declarationNameMismatch,
  formatNric,
  formatPhone,
  isValidPhone,
  eligiblePathways,
  PATHWAY_ORDER,
  programmesForPathway,
  isProgrammePathway,
  isInstitutionPathway,
  eligibleMatricTracks,
  STPM_STREAMS,
  stpmDegreesToCourses,
  UNCERTAINTY_REASONS,
  nricChanged,
  emptyDetailsForm,
  applicationToDetailsForm,
  buildDetailsPayload,
  DOC_TYPES,
  COMPULSORY_DOC_TYPES,
  INCOME_PROOF_TYPES,
  OTHER_OPTIONAL_DOC_TYPES,
  documentsComplete,
  formatFileSize,
  REFERRING_ORG_OPTIONS,
  CALL_LANGUAGE_OPTIONS,
  MALAYSIAN_STATES,
  stashApplyForm,
  popApplyStash,
  peekApplyStash,
  hasApplyReturn,
  clearApplyReturn,
  APPLY_STASH_KEY,
  APPLY_RETURN_KEY,
  NEXT_STEP_ORDER,
  defaultNextTab,
  type ApplyFormState,
} from '@/lib/scholarship'
import type { StudentProfile, ScholarshipApplication, EligibleCourse, PathwayResult, StpmEligibleCourse } from '@/lib/api'
import { collegesForTrack } from '@/data/matric-colleges'
import { stpmSchoolsForStream, STPM_SCHOOLS } from '@/data/stpm-schools'

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
    // My Plans
    pathwayCertainty: 'sure',
    chosenPathway: 'poly',
    chosenProgramme: { courseId: 'C1', courseName: 'Diploma in Engineering', fieldKey: 'engineering' },
    preUTrack: '',
    preUInstitution: '',
    uncertaintyReasons: [],
    uncertaintyNote: '',
    pathwaysConsidered: [],
    topChoices: [],
    upuStatus: '',
    fieldOfStudy: '',
    otherScholarships: [],
    otherScholarshipsText: '',
    intendsTertiary2026: true,
    // My Support
    helpUniversity: '',
    helpScholarship: '',
    anythingElse: '',
    consentToContact: true,
    declarationName: 'Priya',   // matches `name` so a complete form passes with no mismatch
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
    expect(p.intends_tertiary_2026).toBe(true)
    expect(p.consent_to_contact).toBe(true)
    expect(p.declaration_name).toBe('Priya')   // typed signature, trimmed
    expect(p.form_data).toEqual({})
    // academic data + NRIC are never posted here (profile / claim path)
    expect(p.spm_a_count).toBeUndefined()
    expect(p.nric).toBeUndefined()
    expect(p.intended_pathway).toBeUndefined()  // superseded by pathways_considered
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
  it('maps the decided pathway (certainty + chosen pathway)', () => {
    const p = buildApplicationPayload(baseForm({ pathwayCertainty: 'sure', chosenPathway: 'poly' })) as Record<string, unknown>
    expect(p.pathway_certainty).toBe('sure')
    expect(p.chosen_pathway).toBe('poly')
  })
  it('maps the chosen programme to a JSON object (and {} when none)', () => {
    const p = buildApplicationPayload(baseForm({
      chosenProgramme: { courseId: 'DKA', courseName: 'Diploma Kejuruteraan Awam', fieldKey: 'engineering' },
    })) as Record<string, unknown>
    expect(p.chosen_programme).toEqual({ course_id: 'DKA', course_name: 'Diploma Kejuruteraan Awam', field_key: 'engineering' })
    const none = buildApplicationPayload(baseForm({ chosenProgramme: null })) as Record<string, unknown>
    expect(none.chosen_programme).toEqual({})
  })
  it('maps the institution pathway (pre-U track/stream + institution)', () => {
    const p = buildApplicationPayload(baseForm({ chosenPathway: 'matric', preUTrack: 'sains', preUInstitution: 'KM Perak' })) as Record<string, unknown>
    expect(p.pre_u_track).toBe('sains')
    expect(p.pre_u_institution).toBe('KM Perak')
  })
  it('maps the Uncertain branch (reasons + trimmed note)', () => {
    const p = buildApplicationPayload(baseForm({
      pathwayCertainty: 'uncertain', uncertaintyReasons: ['guidance', 'finance'], uncertaintyNote: '  still thinking  ',
    })) as Record<string, unknown>
    expect(p.uncertainty_reasons).toEqual(['guidance', 'finance'])
    expect(p.uncertainty_note).toBe('still thinking')
  })
  it('maps My Plans + My Support (ranks top-3 by order, trims text, empty form_data)', () => {
    const p = buildApplicationPayload(baseForm({
      pathwaysConsidered: ['matrik', 'stpm'],
      topChoices: [
        { courseId: 'C1', courseName: 'Medicine', institution: 'UM' },
        { courseId: 'C2', courseName: 'Pharmacy', institution: 'USM' },
      ],
      upuStatus: 'applied',
      fieldOfStudy: 'health',
      otherScholarships: ['jpa', 'mara'],
      otherScholarshipsText: '  Yayasan X  ',
      helpUniversity: 'yes',
      helpScholarship: 'unsure',
      anythingElse: '  single parent  ',
    })) as Record<string, unknown>
    expect(p.pathways_considered).toEqual(['matrik', 'stpm'])
    expect(p.top_choices).toEqual([
      { rank: 1, course_id: 'C1', course_name: 'Medicine', institution: 'UM' },
      { rank: 2, course_id: 'C2', course_name: 'Pharmacy', institution: 'USM' },
    ])
    expect(p.upu_status).toBe('applied')
    expect(p.field_of_study).toBe('health')
    expect(p.other_scholarships).toEqual(['jpa', 'mara'])
    expect(p.other_scholarships_text).toBe('Yayasan X')
    expect(p.help_university).toBe('yes')
    expect(p.help_scholarship).toBe('unsure')
    expect(p.anything_else).toBe('single parent')
    expect(p.form_data).toEqual({})
  })
  it('drops empty top-3 slots and re-sequences ranks', () => {
    // STPM "still deciding" picker holds 3 fixed slots; a student may leave gaps.
    const p = buildApplicationPayload(baseForm({
      topChoices: [
        null,
        { courseId: 'C2', courseName: 'Pharmacy', institution: 'USM' },
        null,
      ],
    })) as Record<string, unknown>
    expect(p.top_choices).toEqual([
      { rank: 1, course_id: 'C2', course_name: 'Pharmacy', institution: 'USM' },
    ])
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
  it('requires household size of at least 1 (per-capita needs it)', () => {
    expect(applyFormError(baseForm({ householdSize: '' }))).toBe('householdSize')
    expect(applyFormError(baseForm({ householdSize: '0' }))).toBe('householdSize')
    expect(applyFormError(baseForm({ householdSize: '4' }))).toBeNull()
  })
  it('requires household income', () => {
    expect(applyFormError(baseForm({ householdIncome: '' }))).toBe('income')
  })
  it('requires the signed declaration', () => {
    expect(applyFormError(baseForm({ declarationName: '' }))).toBe('declaration')
    expect(applyFormError(baseForm({ declarationName: '   ' }))).toBe('declaration')
    // consent is checked before the declaration
    expect(applyFormError(baseForm({ consentToContact: false, declarationName: '' }))).toBe('consent')
  })
  it('requires consent', () => {
    expect(applyFormError(baseForm({ consentToContact: false }))).toBe('consent')
  })
  it('surfaces the earliest-tab problem first', () => {
    // both name and consent are wrong → About Me wins (earlier tab)
    expect(applyFormError(baseForm({ name: '', consentToContact: false }))).toBe('name')
  })
})

describe('declarationNameMismatch', () => {
  it('is false when the signature matches the name (case/space-insensitive)', () => {
    expect(declarationNameMismatch(baseForm({ name: 'Priya', declarationName: 'Priya' }))).toBe(false)
    expect(declarationNameMismatch(baseForm({ name: 'Priya  Devi', declarationName: ' priya devi ' }))).toBe(false)
  })
  it('is true when the signature differs from the name', () => {
    expect(declarationNameMismatch(baseForm({ name: 'Priya Devi', declarationName: 'Priya' }))).toBe(true)
  })
  it('is false (no nudge) when either field is empty — the required-check handles empties', () => {
    expect(declarationNameMismatch(baseForm({ name: 'Priya', declarationName: '' }))).toBe(false)
    expect(declarationNameMismatch(baseForm({ name: '', declarationName: 'Priya' }))).toBe(false)
  })
})

describe('applyFormError — Plans pathway question', () => {
  it('requires the student to answer whether they have decided', () => {
    expect(applyFormError(baseForm({ pathwayCertainty: '' }))).toBe('pathwayCertainty')
  })
  it('"uncertain" is always a valid answer (never traps an unsure student)', () => {
    expect(applyFormError(baseForm({ pathwayCertainty: 'uncertain', chosenPathway: '' }))).toBeNull()
  })
  it('a decided SPM leaver must pick a pathway', () => {
    expect(applyFormError(baseForm({ pathwayCertainty: 'sure', chosenPathway: '' }))).toBe('chosenPathway')
    expect(applyFormError(baseForm({ pathwayCertainty: 'sure', chosenPathway: 'poly' }))).toBeNull()
  })
  it('exempts STPM students from the pathway requirement (their degree branch is separate)', () => {
    expect(applyFormError(baseForm({ pathwayCertainty: 'sure', chosenPathway: '' }), 'stpm')).toBeNull()
    expect(applyFormError(baseForm({ pathwayCertainty: 'sure', chosenPathway: '' }), 'spm')).toBe('chosenPathway')
  })
  it('the Plans question sits between My Family and consent in error order', () => {
    // income (My Family) is earlier than the pathway question → income wins
    expect(applyFormError(baseForm({ householdIncome: '', pathwayCertainty: '' }))).toBe('income')
    // pathway question is earlier than consent → pathway wins
    expect(applyFormError(baseForm({ pathwayCertainty: '', consentToContact: false }))).toBe('pathwayCertainty')
  })
  it('a decided programme pathway needs the one chosen course', () => {
    expect(applyFormError(baseForm({ chosenPathway: 'poly', chosenProgramme: null }))).toBe('chosenProgramme')
    expect(applyFormError(baseForm({ chosenPathway: 'poly', chosenProgramme: { courseId: 'C1', courseName: 'X', fieldKey: 'f' } }))).toBeNull()
  })
  it('institution pathways (matric/stpm) need a track + institution, not a course', () => {
    // no course required (chosenProgramme stays null); the track + institution are
    expect(applyFormError(baseForm({ chosenPathway: 'matric', chosenProgramme: null, preUTrack: 'sains', preUInstitution: 'KM Perak' }))).toBeNull()
    expect(applyFormError(baseForm({ chosenPathway: 'stpm', chosenProgramme: null, preUTrack: 'sains', preUInstitution: 'SMK X' }))).toBeNull()
  })
  it('a decided institution pathway needs the track/stream, then the college/school', () => {
    expect(applyFormError(baseForm({ chosenPathway: 'matric', preUTrack: '', preUInstitution: '' }))).toBe('preUTrack')
    expect(applyFormError(baseForm({ chosenPathway: 'matric', preUTrack: 'sains', preUInstitution: '' }))).toBe('preUInstitution')
    expect(applyFormError(baseForm({ chosenPathway: 'matric', preUTrack: 'sains', preUInstitution: 'KM Perak' }))).toBeNull()
    expect(applyFormError(baseForm({ chosenPathway: 'stpm', preUTrack: '', preUInstitution: '' }))).toBe('preUTrack')
    // "not sure" stream is valid; a school is still required
    expect(applyFormError(baseForm({ chosenPathway: 'stpm', preUTrack: 'not_sure', preUInstitution: 'SMK X' }))).toBeNull()
  })
  it('STPM students are exempt from the SPM institution requirement (they pick a degree)', () => {
    // no preU track/institution needed; instead a decided STPM student must pick a degree
    expect(applyFormError(baseForm({ chosenPathway: '', preUTrack: '', preUInstitution: '', chosenProgramme: null }), 'stpm')).toBe('chosenProgramme')
    expect(applyFormError(baseForm({ chosenPathway: '', preUTrack: '', preUInstitution: '', chosenProgramme: { courseId: 'D1', courseName: 'BSc', fieldKey: 'science' } }), 'stpm')).toBeNull()
  })
  it('the Uncertain branch never blocks (leanings/reasons/note all optional)', () => {
    expect(applyFormError(baseForm({ pathwayCertainty: 'uncertain', chosenPathway: '', chosenProgramme: null, uncertaintyReasons: [], uncertaintyNote: '' }))).toBeNull()
    expect(applyFormError(baseForm({ pathwayCertainty: 'uncertain', chosenPathway: '', chosenProgramme: null }), 'stpm')).toBeNull()
  })
})

describe('stpmDegreesToCourses', () => {
  const degrees = [
    { course_id: 'z', course_name: 'Zoology', university: 'UM', field: 'science', field_key: 'science' },
    { course_id: 'a', course_name: 'Accounting', university: 'USM', field: 'business', field_key: 'business' },
  ] as unknown as StpmEligibleCourse[]
  it('maps to the course shape (university → institution) and sorts A–Z', () => {
    const out = stpmDegreesToCourses(degrees)
    expect(out.map((c) => c.course_name)).toEqual(['Accounting', 'Zoology'])
    expect(out[0].institution_name).toBe('USM')
    expect(out[0].field_key).toBe('business')
  })
  it('handles null/empty', () => {
    expect(stpmDegreesToCourses(null)).toEqual([])
    expect(stpmDegreesToCourses([])).toEqual([])
  })
})

describe('UNCERTAINTY_REASONS', () => {
  it('lists the five "where are you right now?" reasons', () => {
    expect(UNCERTAINTY_REASONS).toEqual(['exploring', 'results', 'guidance', 'family', 'finance'])
  })
})

describe('isInstitutionPathway', () => {
  it('is true only for matriculation + STPM', () => {
    expect(isInstitutionPathway('matric')).toBe(true)
    expect(isInstitutionPathway('stpm')).toBe(true)
    expect(isInstitutionPathway('poly')).toBe(false)
    expect(isInstitutionPathway('')).toBe(false)
  })
})

describe('eligibleMatricTracks', () => {
  const pathways = [
    { pathway: 'matric', trackId: 'sains', eligible: true },
    { pathway: 'matric', trackId: 'kejuruteraan', eligible: false },
    { pathway: 'matric', trackId: 'perakaunan', eligible: true },
    { pathway: 'stpm', trackId: 'sains', eligible: true },
  ] as unknown as PathwayResult[]
  it('returns eligible matric track ids in order, ignoring ineligible + stpm', () => {
    expect(eligibleMatricTracks(pathways)).toEqual(['sains', 'perakaunan'])
  })
  it('handles null/empty', () => {
    expect(eligibleMatricTracks(null)).toEqual([])
    expect(eligibleMatricTracks([])).toEqual([])
  })
})

describe('STPM_STREAMS', () => {
  it('offers science, social science, and a not-sure escape', () => {
    expect(STPM_STREAMS).toEqual(['sains', 'sains_sosial', 'not_sure'])
  })
})

describe('collegesForTrack (matric data)', () => {
  it('returns only colleges offering the track', () => {
    const eng = collegesForTrack('kejuruteraan')
    expect(eng.length).toBeGreaterThan(0)
    expect(eng.every((c) => (c.tracks as string[]).includes('kejuruteraan'))).toBe(true)
    // science is offered far more widely than the engineering-only colleges
    expect(collegesForTrack('sains').length).toBeGreaterThan(eng.length)
    expect(collegesForTrack('nope')).toEqual([])
  })
})

describe('stpmSchoolsForStream (STPM data)', () => {
  it('filters by stream label, and returns every centre for not_sure', () => {
    const sains = stpmSchoolsForStream('sains')
    expect(sains.length).toBeGreaterThan(0)
    expect(sains.every((s) => s.streams.includes('Sains'))).toBe(true)
    expect(stpmSchoolsForStream('sains_sosial').every((s) => s.streams.includes('Sains Sosial'))).toBe(true)
    expect(stpmSchoolsForStream('not_sure').length).toBe(STPM_SCHOOLS.length)
  })
})

describe('isProgrammePathway', () => {
  it('is true for the seven programme-list pathways', () => {
    for (const k of ['asasi', 'university', 'poly', 'kkom', 'pismp', 'iljtm', 'ilkbs']) {
      expect(isProgrammePathway(k)).toBe(true)
    }
  })
  it('is false for the institution pathways (matric/stpm) and unknowns', () => {
    expect(isProgrammePathway('matric')).toBe(false)
    expect(isProgrammePathway('stpm')).toBe(false)
    expect(isProgrammePathway('')).toBe(false)
    expect(isProgrammePathway('foo')).toBe(false)
  })
})

describe('programmesForPathway', () => {
  const courses = [
    { course_id: '1', course_name: 'Zoology', pathway_type: 'university' },
    { course_id: '2', course_name: 'Accounting', pathway_type: 'poly' },
    { course_id: '3', course_name: 'Botany', pathway_type: 'university' },
    { course_id: '4', course_name: 'Welding', pathway_type: 'poly' },
  ] as unknown as EligibleCourse[]
  it('filters to the chosen pathway and sorts alphabetically by name', () => {
    expect(programmesForPathway(courses, 'poly').map((c) => c.course_name)).toEqual(['Accounting', 'Welding'])
    expect(programmesForPathway(courses, 'university').map((c) => c.course_name)).toEqual(['Botany', 'Zoology'])
  })
  it('returns [] for a pathway with no eligible courses, or null/empty input', () => {
    expect(programmesForPathway(courses, 'pismp')).toEqual([])
    expect(programmesForPathway(null, 'poly')).toEqual([])
    expect(programmesForPathway(courses, '')).toEqual([])
  })
})

describe('formatNric', () => {
  it('inserts dashes as digits are typed', () => {
    expect(formatNric('0')).toBe('0')
    expect(formatNric('050202')).toBe('050202')
    expect(formatNric('05020202')).toBe('050202-02')
    expect(formatNric('050202022022')).toBe('050202-02-2022')
  })
  it('strips non-digits and caps at 12 digits', () => {
    expect(formatNric('050202-02-2022')).toBe('050202-02-2022') // idempotent
    expect(formatNric('05 0202 02 2022')).toBe('050202-02-2022')
    expect(formatNric('050202022022999')).toBe('050202-02-2022') // overflow trimmed
    expect(formatNric('abc')).toBe('')
  })
  it('produces a value applyFormError accepts once 12 digits are present', () => {
    expect(applyFormError(baseForm({ nric: formatNric('050202022022') }))).not.toBe('nric')
  })
})

describe('formatPhone', () => {
  it('groups digits as 0XX-XXX XXXX as they are typed', () => {
    expect(formatPhone('01')).toBe('01')
    expect(formatPhone('0123')).toBe('012-3')
    expect(formatPhone('0123456')).toBe('012-3456')
    expect(formatPhone('0123456789')).toBe('012-345 6789')   // 10 digits
    expect(formatPhone('01123456789')).toBe('011-2345 6789') // 11 digits
  })
  it('strips non-digits, is idempotent, and caps at 11 digits', () => {
    expect(formatPhone('012-345 6789')).toBe('012-345 6789') // idempotent
    expect(formatPhone('012 345 6789')).toBe('012-345 6789') // spaces normalised
    expect(formatPhone('0123456789999')).toBe('012-3456 7899') // 13 digits -> 11
  })
  it('is landline-aware (area code 2 or 3 digits by region)', () => {
    expect(formatPhone('0312345678')).toBe('03-1234 5678')  // Klang Valley
    expect(formatPhone('041234567')).toBe('04-123 4567')    // Penang
    expect(formatPhone('092345678')).toBe('09-234 5678')    // East coast
    expect(formatPhone('088123456')).toBe('088-123 456')    // Sabah/Sarawak 08X
    expect(formatPhone('03-1234 5678')).toBe('03-1234 5678') // idempotent
    expect(formatPhone('088-123 456')).toBe('088-123 456')  // idempotent
  })
})

describe('isValidPhone', () => {
  it('accepts 9–11 digit numbers starting with 0', () => {
    expect(isValidPhone('012-345 6789')).toBe(true)
    expect(isValidPhone('011-2345 6789')).toBe(true)
    expect(isValidPhone('03-1234 5678')).toBe(true)
  })
  it('rejects too-short, non-zero-leading, or empty', () => {
    expect(isValidPhone('')).toBe(false)
    expect(isValidPhone('12345')).toBe(false)
    expect(isValidPhone('12-345 6789')).toBe(false) // no leading 0
  })
})

describe('applyFormError — phone + parent phone', () => {
  it('rejects an invalid or empty applicant phone', () => {
    expect(applyFormError(baseForm({ phone: '' }))).toBe('phone')
    expect(applyFormError(baseForm({ phone: '12345' }))).toBe('phone')
  })
  it('parent phone is optional but validated when present', () => {
    expect(applyFormError(baseForm({ parentPhone: '' }))).toBeNull()
    expect(applyFormError(baseForm({ parentPhone: '012-345 6789' }))).toBeNull()
    expect(applyFormError(baseForm({ parentPhone: '123' }))).toBe('parentPhone')
  })
})

describe('eligiblePathways', () => {
  it('returns count>0 pathways in fixed display order, with counts', () => {
    const res = eligiblePathways({
      poly: 85, asasi: 6, matric: 3, university: 49, kkom: 53, iljtm: 48, ilkbs: 35, stpm: 2,
    })
    expect(res.map((p) => p.key)).toEqual(
      ['matric', 'stpm', 'asasi', 'university', 'poly', 'kkom', 'iljtm', 'ilkbs'])
    expect(res.find((p) => p.key === 'poly')!.count).toBe(85)
  })
  it('drops zero/absent pathways and unknown keys (e.g. un-split tvet)', () => {
    expect(eligiblePathways({ poly: 0, tvet: 10, pismp: 3 })).toEqual([{ key: 'pismp', count: 3 }])
  })
  it('handles null/empty input', () => {
    expect(eligiblePathways(null)).toEqual([])
    expect(eligiblePathways({})).toEqual([])
  })
  it('only ever emits keys from PATHWAY_ORDER', () => {
    const keys = eligiblePathways({ matric: 1, foo: 9, bar: 2 }).map((p) => p.key)
    expect(keys.every((k) => (PATHWAY_ORDER as readonly string[]).includes(k))).toBe(true)
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

  it('peeks the stash without consuming it (onboarding detour can read it then apply page still pops it)', () => {
    const s = fakeStorage()
    const form = baseForm({ homeState: 'Johor' })
    stashApplyForm(form, s)
    // peek twice — value stays
    expect(peekApplyStash(s)?.homeState).toBe('Johor')
    expect(peekApplyStash(s)?.homeState).toBe('Johor')
    // pop still works after peeks
    expect(popApplyStash(s)?.homeState).toBe('Johor')
    expect(peekApplyStash(s)).toBeNull()
  })

  it('peekApplyStash returns null on missing / unparseable / no-storage', () => {
    const s = fakeStorage()
    expect(peekApplyStash(s)).toBeNull()
    s.setItem(APPLY_STASH_KEY, '{not json')
    expect(peekApplyStash(s)).toBeNull()
    expect(peekApplyStash()).toBeNull()
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
    // 9 partner orgs (smc/cumig/ewrf/hyo/mhm/sathya_sai/tara/hss/pptm)
    // + 5 individual/self/generic (pushparani/govind/halatuju/social/other) = 14
    expect(REFERRING_ORG_OPTIONS.length).toBe(14)
    for (const code of ['ewrf', 'hyo', 'mhm', 'hss', 'pptm']) {
      expect(REFERRING_ORG_OPTIONS).toContain(code)
    }
  })
  it('offers the four call languages and the 16 states', () => {
    expect(CALL_LANGUAGE_OPTIONS).toEqual(['en', 'ms', 'ta', 'mixed'])
    expect(MALAYSIAN_STATES).toContain('Selangor')
    expect(MALAYSIAN_STATES.length).toBe(16)
  })
})

describe('buildDetailsPayload', () => {
  it('trims story text fields and maps them to snake_case', () => {
    const f = { ...emptyDetailsForm(), aspirations: '  be a teacher ' }
    const p = buildDetailsPayload(f) as { aspirations: string }
    expect(p.aspirations).toBe('be a teacher')
  })

  it('includes all 5 new story snake_case fields', () => {
    const f = {
      ...emptyDetailsForm(),
      firstInFamily: true,
      parentsOccupation: '  Factory worker  ',
      familyContext: '  Father is ill  ',
      dailyLife: '  Wake at 5am  ',
    }
    const p = buildDetailsPayload(f) as Record<string, unknown>
    expect(p.first_in_family).toBe(true)
    expect(p.parents_occupation).toBe('Factory worker')
    expect(p.family_context).toBe('Father is ill')
    expect(p.daily_life).toBe('Wake at 5am')
    // S15: the form no longer emits the legacy boolean; back-compat lives
    // on the backend serializer only.
    expect('siblings_studying' in p).toBe(false)
  })

  it('S15: emits siblings_studying_count as int|null (string-to-int conversion)', () => {
    // empty string → null
    let p = buildDetailsPayload(emptyDetailsForm()) as Record<string, unknown>
    expect(p.siblings_studying_count).toBeNull()
    // "3" → 3
    p = buildDetailsPayload({ ...emptyDetailsForm(), siblingsStudyingCount: '3' }) as Record<string, unknown>
    expect(p.siblings_studying_count).toBe(3)
    // "0" → 0 (a valid answer — no siblings studying)
    p = buildDetailsPayload({ ...emptyDetailsForm(), siblingsStudyingCount: '0' }) as Record<string, unknown>
    expect(p.siblings_studying_count).toBe(0)
    // whitespace stripped
    p = buildDetailsPayload({ ...emptyDetailsForm(), siblingsStudyingCount: '  2  ' }) as Record<string, unknown>
    expect(p.siblings_studying_count).toBe(2)
  })

  it('emits S3 funding fields: categories, funding_note, programme_months (trimmed, typed)', () => {
    const f = {
      ...emptyDetailsForm(),
      fundingCategories: ['living', 'transport'],
      fundingNote: '  I will try for PTPTN.  ',
      programmeMonths: '36',
    }
    const p = buildDetailsPayload(f) as Record<string, unknown>
    const fn = p.funding_need as Record<string, unknown>
    expect(fn.categories).toEqual(['living', 'transport'])
    expect(fn.funding_note).toBe('I will try for PTPTN.')
    expect(fn.programme_months).toBe(36)
  })

  it('converts blank programmeMonths to null', () => {
    const f = { ...emptyDetailsForm(), programmeMonths: '' }
    const fn = (buildDetailsPayload(f) as Record<string, unknown>).funding_need as Record<string, unknown>
    expect(fn.programme_months).toBeNull()
  })

  it('sends empty categories when none ticked', () => {
    const f = { ...emptyDetailsForm(), fundingCategories: [] }
    const fn = (buildDetailsPayload(f) as Record<string, unknown>).funding_need as Record<string, unknown>
    expect(fn.categories).toEqual([])
  })

  it('includes trimmed address fields (S14) so the backend writes them to the profile', () => {
    const f = {
      ...emptyDetailsForm(),
      address: '  No. 12, Jalan ABC, Taman XYZ  ',
      postalCode: ' 62100 ',
      city: ' Putrajaya ',
    }
    const p = buildDetailsPayload(f) as Record<string, unknown>
    expect(p.address).toBe('No. 12, Jalan ABC, Taman XYZ')
    expect(p.postal_code).toBe('62100')
    expect(p.city).toBe('Putrajaya')
  })

  it('sends empty strings when address fields are blank (no nulls)', () => {
    const p = buildDetailsPayload(emptyDetailsForm()) as Record<string, unknown>
    expect(p.address).toBe('')
    expect(p.postal_code).toBe('')
    expect(p.city).toBe('')
  })
})

describe('applicationToDetailsForm', () => {
  it('pre-fills story + funding from an application with a funding need', () => {
    const app = {
      aspirations: 'Teach', plans: '', fears: '', justification: 'Need help',
      first_in_family: false, parents_occupation: '', siblings_studying: false,
      family_context: '', daily_life: '',
      funding_need: {
        categories: ['living'], funding_note: 'note', programme_months: 12,
      },
    } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.aspirations).toBe('Teach')
    expect(f.justification).toBe('Need help')
    expect(f.fundingCategories).toEqual(['living'])
    expect(f.fundingNote).toBe('note')
    expect(f.programmeMonths).toBe('12')
    // new story fields
    expect(f.firstInFamily).toBe(false)
    expect(f.parentsOccupation).toBe('')
    expect(f.dailyLife).toBe('')
  })
  it('reads back story narrative fields from an application', () => {
    const app = {
      aspirations: 'Be a nurse', plans: 'Study pharmacy', fears: '', justification: '',
      first_in_family: true, parents_occupation: 'Rubber tapper',
      siblings_studying: true, siblings_studying_count: 3,
      family_context: 'Mother is ill',
      daily_life: 'Wake early, help at home',
      funding_need: null,
    } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.firstInFamily).toBe(true)
    expect(f.parentsOccupation).toBe('Rubber tapper')
    expect(f.siblingsStudyingCount).toBe('3')
    expect(f.familyContext).toBe('Mother is ill')
    expect(f.dailyLife).toBe('Wake early, help at home')
  })

  it('S15: pre-fills siblingsStudyingCount from app.siblings_studying_count when set', () => {
    const app = {
      aspirations: '', plans: '', fears: '', justification: '',
      first_in_family: false, parents_occupation: '',
      siblings_studying: false, siblings_studying_count: 0,
      family_context: '', daily_life: '', funding_need: null,
    } as unknown as ScholarshipApplication
    expect(applicationToDetailsForm(app).siblingsStudyingCount).toBe('0')
  })

  it('S15: falls back to "1" when only the legacy boolean is true (older data)', () => {
    const app = {
      aspirations: '', plans: '', fears: '', justification: '',
      first_in_family: false, parents_occupation: '',
      siblings_studying: true, siblings_studying_count: null,
      family_context: '', daily_life: '', funding_need: null,
    } as unknown as ScholarshipApplication
    expect(applicationToDetailsForm(app).siblingsStudyingCount).toBe('1')
  })

  it('S15: empty when neither count nor boolean indicates studying siblings', () => {
    const app = {
      aspirations: '', plans: '', fears: '', justification: '',
      first_in_family: false, parents_occupation: '',
      siblings_studying: false, siblings_studying_count: null,
      family_context: '', daily_life: '', funding_need: null,
    } as unknown as ScholarshipApplication
    expect(applicationToDetailsForm(app).siblingsStudyingCount).toBe('')
  })
  it('handles a null funding need', () => {
    const app = {
      aspirations: '', plans: '', fears: '', justification: '',
      first_in_family: false, parents_occupation: '', siblings_studying: false,
      family_context: '', daily_life: '',
      funding_need: null,
    } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.fundingCategories).toEqual([])
    expect(f.fundingNote).toBe('')
    expect(f.aspirations).toBe('')
    expect(f.firstInFamily).toBe(false)
  })

  it('reads back S3 funding fields from a funding_need row', () => {
    const app = {
      aspirations: '', plans: '', fears: '', justification: '',
      first_in_family: false, parents_occupation: '', siblings_studying: false,
      family_context: '', daily_life: '',
      funding_need: {
        categories: ['living', 'books'],
        funding_note: 'I will apply for PTPTN.',
        programme_months: 48,
      },
    } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.fundingCategories).toEqual(['living', 'books'])
    expect(f.fundingNote).toBe('I will apply for PTPTN.')
    expect(f.programmeMonths).toBe('48')
  })

  it('defaults S3 fields when funding_need is null', () => {
    const app = {
      aspirations: '', plans: '', fears: '', justification: '',
      first_in_family: false, parents_occupation: '', siblings_studying: false,
      family_context: '', daily_life: '',
      funding_need: null,
    } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.fundingCategories).toEqual([])
    expect(f.fundingNote).toBe('')
    expect(f.programmeMonths).toBe('')
  })

  it('pre-fills S14 address fields from the profile-derived application response', () => {
    const app = {
      aspirations: '', plans: '', fears: '', justification: '',
      first_in_family: false, parents_occupation: '', siblings_studying: false,
      family_context: '', daily_life: '',
      funding_need: null,
      address: 'No. 12, Jalan ABC', postal_code: '62100', city: 'Putrajaya',
      preferred_state: 'W.P. Putrajaya',
    } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.address).toBe('No. 12, Jalan ABC')
    expect(f.postalCode).toBe('62100')
    expect(f.city).toBe('Putrajaya')
  })

  it('defaults S14 address fields to empty when the application has no address yet', () => {
    const app = {
      aspirations: '', plans: '', fears: '', justification: '',
      first_in_family: false, parents_occupation: '', siblings_studying: false,
      family_context: '', daily_life: '',
      funding_need: null,
    } as unknown as ScholarshipApplication
    const f = applicationToDetailsForm(app)
    expect(f.address).toBe('')
    expect(f.postalCode).toBe('')
    expect(f.city).toBe('')
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
  it('lists all supporting document types including the four new S4 types', () => {
    // 2 compulsory + 3 income proof + 5 other optional + reference_letter = 11
    expect(DOC_TYPES).toHaveLength(11)
    expect(DOC_TYPES).toContain('ic')
    expect(DOC_TYPES).toContain('reference_letter')
    expect(DOC_TYPES).toContain('salary_slip')
    expect(DOC_TYPES).toContain('water_bill')
    expect(DOC_TYPES).toContain('electricity_bill')
    expect(DOC_TYPES).toContain('offer_letter')
  })
})

describe('COMPULSORY_DOC_TYPES / INCOME_PROOF_TYPES / OTHER_OPTIONAL_DOC_TYPES', () => {
  it('has ic and results_slip as compulsory', () => {
    expect(COMPULSORY_DOC_TYPES).toContain('ic')
    expect(COMPULSORY_DOC_TYPES).toContain('results_slip')
    expect(COMPULSORY_DOC_TYPES).toHaveLength(2)
  })

  it('has three income proof types', () => {
    expect(INCOME_PROOF_TYPES).toContain('str')
    expect(INCOME_PROOF_TYPES).toContain('salary_slip')
    expect(INCOME_PROOF_TYPES).toContain('epf')
    expect(INCOME_PROOF_TYPES).toHaveLength(3)
  })

  it('has five other optional doc types', () => {
    expect(OTHER_OPTIONAL_DOC_TYPES).toContain('water_bill')
    expect(OTHER_OPTIONAL_DOC_TYPES).toContain('electricity_bill')
    expect(OTHER_OPTIONAL_DOC_TYPES).toContain('offer_letter')
    expect(OTHER_OPTIONAL_DOC_TYPES).toHaveLength(5)
  })
})

describe('documentsComplete', () => {
  it('returns true when both ic and results_slip are present', () => {
    expect(documentsComplete(['ic', 'results_slip'])).toBe(true)
  })

  it('returns true with extra doc types alongside the two compulsory', () => {
    expect(documentsComplete(['ic', 'results_slip', 'salary_slip', 'photo'])).toBe(true)
  })

  it('returns false when no documents are present', () => {
    expect(documentsComplete([])).toBe(false)
  })

  it('returns false when only ic is present', () => {
    expect(documentsComplete(['ic'])).toBe(false)
  })

  it('returns false when only results_slip is present', () => {
    expect(documentsComplete(['results_slip'])).toBe(false)
  })

  it('returns false when neither compulsory type is present', () => {
    expect(documentsComplete(['salary_slip', 'photo', 'epf'])).toBe(false)
  })
})

// ── S1: next-steps tabbed shell helpers ─────────────────────────────────

describe('NEXT_STEP_ORDER', () => {
  it('has exactly 5 tabs in the correct order', () => {
    expect(NEXT_STEP_ORDER).toEqual(['quiz', 'story', 'funding', 'documents', 'consent'])
  })

  it('does not include referee', () => {
    expect(NEXT_STEP_ORDER).not.toContain('referee')
  })
})

describe('defaultNextTab', () => {
  it('returns quiz when completeness is null', () => {
    expect(defaultNextTab(null)).toBe('quiz')
  })

  it('returns quiz when quiz is not done', () => {
    expect(defaultNextTab({ quiz_done: false, details_done: false, funding_done: false })).toBe('quiz')
  })

  it('returns story when quiz is done but details not done', () => {
    expect(defaultNextTab({ quiz_done: true, details_done: false, funding_done: false })).toBe('story')
  })

  it('returns funding when quiz + story done but funding not done', () => {
    expect(defaultNextTab({ quiz_done: true, details_done: true, funding_done: false })).toBe('funding')
  })

  it('falls back to quiz when all three known steps are done', () => {
    expect(defaultNextTab({ quiz_done: true, details_done: true, funding_done: true })).toBe('quiz')
  })
})
