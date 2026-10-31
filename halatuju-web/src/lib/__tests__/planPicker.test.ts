/**
 * The scholarship "My Plans" picker's pure rules (owner rulings 2026-10-30): institution first,
 * unfiltered unless "Eligible only" passes an `allowed` set, and the pick carrying its institution.
 */
import type { PathwayOfferings } from '@/lib/api'
import {
  DEGREE_PATHWAY, MATRIC_TRACKS, aliranOfCourse, applyPlanPatch, asksStateFirst, coursesAt,
  degreeChoices, institutionKind, institutionOf, isOfferingPathway, noCampusInstitutions,
  offeringInstitutions, offeringStates, pickProgramme, pismpAliransOf, pismpBidang,
} from '@/lib/planPicker'
import en from '@/messages/en.json'
import {
  PATHWAY_ORDER, chosenProgrammeFromApi, chosenProgrammeToApi, profileToApplyDefaults,
} from '@/lib/scholarship'

const POLY: PathwayOfferings = {
  pathway: 'poly',
  institutions: [
    { id: 'PUO', institution_id: 'PUO', name: 'Politeknik Ungku Omar', state: 'Perak', course_ids: ['ELEK', 'MEK'] },
    { id: 'PKB', institution_id: 'PKB', name: 'Politeknik Kota Bharu', state: 'Kelantan', course_ids: ['ELEK'] },
    { id: 'PSA', institution_id: 'PSA', name: 'Politeknik Sultan Azlan Shah', state: 'Perak', course_ids: ['AWAM'] },
  ],
  courses: [
    { course_id: 'MEK', course_name: 'Diploma Kejuruteraan Mekanikal', field_key: 'mek', aliran: null },
    { course_id: 'ELEK', course_name: 'Diploma Kejuruteraan Elektrik', field_key: 'elek', aliran: null },
    { course_id: 'AWAM', course_name: 'Diploma Kejuruteraan Awam', field_key: 'awam', aliran: null },
  ],
}

describe('the steps each pathway asks for', () => {
  it('campus pathways ask for a state first; the university pathways do not', () => {
    for (const p of ['poly', 'kkom', 'mara', 'iljtm', 'ilkbs', 'tvet_other']) expect(asksStateFirst(p)).toBe(true)
    for (const p of ['university', 'asasi', DEGREE_PATHWAY, 'pismp', 'matric', 'stpm']) expect(asksStateFirst(p)).toBe(false)
  })
  it('names the institution step by its kind', () => {
    expect(institutionKind('poly')).toBe('poly')
    expect(institutionKind('mara')).toBe('campus')
    // Asasi and university lists hold polytechnics and MARA too (owner, 2026-10-31).
    expect(institutionKind('university')).toBe('institution')
    expect(institutionKind('asasi')).toBe('institution')
    expect(institutionKind(DEGREE_PATHWAY)).toBe('university')
  })
  it('MARA\'s education division is offered before the states, never inside one (owner, 2026-10-31)', () => {
    const o: PathwayOfferings = {
      pathway: 'mara',
      institutions: [
        { id: 'K', institution_id: 'K', name: 'KKTM Kemaman', state: 'Terengganu', course_ids: ['T1'] },
        { id: 'BPT', institution_id: 'MARA-BPT', name: 'MARA BPT', state: 'WP Kuala Lumpur',
          course_ids: ['OP1', 'OP2'], no_campus: true },
      ],
      courses: [],
    }
    expect(offeringStates(o, null)).toEqual(['Terengganu'])
    expect(offeringInstitutions(o, 'WP Kuala Lumpur', null)).toEqual([])
    expect(noCampusInstitutions(o, null).map((i) => i.id)).toEqual(['BPT'])
    expect(noCampusInstitutions(o, new Set(['OP2'])).map((i) => i.id)).toEqual(['BPT'])   // by course id
    expect(noCampusInstitutions(o, new Set(['T1']))).toEqual([])
  })
  it('the plan\'s pathway labels: "University" and "MARA college or institute"', () => {
    const plan = (en as { scholarship: { apply: { plan: { pathway: Record<string, string>; maraDivision: string } } } })
      .scholarship.apply.plan
    expect(plan.pathway.university).toBe('University')
    expect(plan.pathway.mara).toBe('MARA college or institute')
    expect(plan.maraDivision).toBe('MARA college (Bahagian Pendidikan Tinggi)')
  })
  it('every programme pathway in PATHWAY_ORDER is served by the catalogue; the pre-U two are not', () => {
    for (const p of PATHWAY_ORDER) expect(isOfferingPathway(p)).toBe(p !== 'matric' && p !== 'stpm')
    expect(isOfferingPathway(DEGREE_PATHWAY)).toBe(true)
  })
  it('the four matriculation tracks with colleges, unfiltered', () => {
    expect(MATRIC_TRACKS).toEqual(['sains', 'kejuruteraan', 'sains_komputer', 'perakaunan'])
  })
})

describe('unfiltered by default (allowed = null)', () => {
  it('lists every state, institution and course', () => {
    expect(offeringStates(POLY, null)).toEqual(['Kelantan', 'Perak'])
    // A–Z by name: Politeknik Sultan Azlan Shah, then Politeknik Ungku Omar
    expect(offeringInstitutions(POLY, 'Perak', null).map((i) => i.id)).toEqual(['PSA', 'PUO'])
    expect(coursesAt(POLY, 'PUO', null).map((c) => c.course_name))
      .toEqual(['Diploma Kejuruteraan Elektrik', 'Diploma Kejuruteraan Mekanikal'])
  })
  it('a university pathway lists every institution with no state step', () => {
    expect(offeringInstitutions(POLY, null, null)).toHaveLength(3)
  })
})

describe('"Eligible only" narrows every step to allowed courses', () => {
  const allowed = new Set(['ELEK'])
  it('drops states, institutions and courses with nothing allowed', () => {
    expect(offeringStates(POLY, allowed)).toEqual(['Kelantan', 'Perak'])
    expect(offeringInstitutions(POLY, 'Perak', allowed).map((i) => i.id)).toEqual(['PUO'])
    expect(coursesAt(POLY, 'PUO', allowed).map((c) => c.course_id)).toEqual(['ELEK'])
    expect(offeringStates(POLY, new Set(['AWAM']))).toEqual(['Perak'])
  })
})

describe('the pick carries its institution', () => {
  it('pickProgramme takes the catalogue name and id', () => {
    const inst = POLY.institutions[0]
    expect(pickProgramme(POLY.courses[1], inst)).toEqual({
      courseId: 'ELEK', courseName: 'Diploma Kejuruteraan Elektrik', fieldKey: 'elek',
      institution: 'Politeknik Ungku Omar', institutionId: 'PUO' })
    expect(pickProgramme(POLY.courses[1])).toEqual({ courseId: 'ELEK', courseName: 'Diploma Kejuruteraan Elektrik', fieldKey: 'elek' })
  })
  it('institutionOf re-opens a saved pick by id, else by name', () => {
    const cp = { courseId: 'ELEK', courseName: 'x', fieldKey: '' }
    expect(institutionOf(POLY, { ...cp, institutionId: 'PKB' })?.id).toBe('PKB')
    expect(institutionOf(POLY, { ...cp, institution: 'Politeknik Ungku Omar' })?.id).toBe('PUO')
    expect(institutionOf(POLY, cp)).toBeUndefined()
    expect(institutionOf(null, cp)).toBeUndefined()
  })
  it('round-trips through the stored SNAKE shape, and an old pick keeps three keys', () => {
    const cp = pickProgramme(POLY.courses[1], POLY.institutions[0])
    const api = chosenProgrammeToApi(cp)
    expect(api).toEqual({ course_id: 'ELEK', course_name: 'Diploma Kejuruteraan Elektrik', field_key: 'elek',
      institution: 'Politeknik Ungku Omar', institution_id: 'PUO' })
    expect(chosenProgrammeFromApi(api)).toEqual(cp)
    expect(chosenProgrammeToApi({ courseId: 'A', courseName: 'B', fieldKey: 'c' })).toEqual({ course_id: 'A', course_name: 'B', field_key: 'c' })
    expect(chosenProgrammeToApi(null)).toEqual({})
    expect(chosenProgrammeFromApi({})).toBeNull()
    expect(chosenProgrammeFromApi(null)).toBeNull()
    // an offer-autofilled row keeps its institution when /profile reads it back
    expect(chosenProgrammeFromApi({ course_name: 'Asasi', institution: 'UPM', source: 'offer_letter_auto' }))
      .toEqual({ courseId: '', courseName: 'Asasi', fieldKey: '', institution: 'UPM' })
  })
})

describe('PISMP: school type → subject', () => {
  const PISMP: PathwayOfferings = {
    pathway: 'pismp', institutions: [],
    courses: [
      { course_id: 'T1', course_name: 'Sains (SJKT)', field_key: 'pend', aliran: 'sjkt' },
      { course_id: 'T2', course_name: 'Matematik (SJKT)', field_key: 'pend', aliran: 'sjkt' },
      { course_id: 'T3', course_name: 'Matematik (SJKT)', field_key: 'pend', aliran: 'sjkt' },   // a zone variant
      { course_id: 'K1', course_name: 'Bahasa Inggeris (SK)', field_key: 'pend', aliran: 'sk' },
    ],
  }
  it('lists the school types present, in display order', () => {
    expect(pismpAliransOf(PISMP, null)).toEqual(['sk', 'sjkt'])
    expect(pismpAliransOf(PISMP, new Set(['T1']))).toEqual(['sjkt'])
  })
  it('lists one row per subject name, A–Z', () => {
    expect(pismpBidang(PISMP, 'sjkt', null).map((c) => c.course_name)).toEqual(['Matematik (SJKT)', 'Sains (SJKT)'])
    expect(pismpBidang(PISMP, 'sjkt', new Set(['T3'])).map((c) => c.course_id)).toEqual(['T3'])
    expect(pismpBidang(PISMP, '', null)).toEqual([])
  })
  it('re-opens on the school type of a saved pick', () => {
    expect(aliranOfCourse(PISMP, 'K1')).toBe('sk')
    expect(aliranOfCourse(PISMP, 'nope')).toBe('')
    expect(aliranOfCourse(null, 'K1')).toBe('')
  })
})

it('the waiting branch top-3 lists every degree with its university', () => {
  const DEG: PathwayOfferings = {
    pathway: DEGREE_PATHWAY,
    institutions: [{ id: 'UITM', institution_id: 'UITM', name: 'Universiti Teknologi MARA', state: 'Selangor', course_ids: ['L1'] }],
    courses: [{ course_id: 'L1', course_name: 'Ijazah Undang-Undang', field_key: 'law', aliran: null }],
  }
  expect(degreeChoices(DEG, null)).toEqual([{ ...DEG.courses[0], institution_name: 'Universiti Teknologi MARA' }])
  expect(degreeChoices(DEG, new Set())).toEqual([])
})

describe('applyPlanPatch: the apply form\'s derived answers follow the picker', () => {
  const form = profileToApplyDefaults(null)
  it('a named pathway is a public destination; none clears it', () => {
    expect(applyPlanPatch(form, { chosenPathway: 'poly' }).upuStatus).toBe('public_other')
    expect(applyPlanPatch({ ...form, upuStatus: 'public_other' }, { chosenPathway: '' }).upuStatus).toBe('')
  })
  it('the course sets the field of study; clearing it clears the field', () => {
    const cp = { courseId: 'A', courseName: 'B', fieldKey: 'eng', institution: 'X', institutionId: 'Y' }
    const next = applyPlanPatch(form, { chosenProgramme: cp })
    expect(next.fieldOfStudy).toBe('eng')
    expect(next.chosenProgramme).toBe(cp)
    expect(applyPlanPatch(next, { chosenProgramme: null }).fieldOfStudy).toBe('')
  })
  it('an unrelated patch leaves both alone', () => {
    const base = { ...form, upuStatus: 'public_other' as const, fieldOfStudy: 'eng' }
    const next = applyPlanPatch(base, { uncertaintyReasons: ['results'] })
    expect(next.upuStatus).toBe('public_other')
    expect(next.fieldOfStudy).toBe('eng')
  })
})
