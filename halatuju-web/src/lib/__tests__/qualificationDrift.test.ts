/**
 * THE DRIFT TEST for the results-route vocabulary (third results route S2b, 2026-10-26).
 *
 * `lib/qualification.ts` names the five qualification codes a results form can complete, and
 * `lib/sponsorFilter.ts` reads the sponsor card's academic line by the server's plain names. Both
 * are copies of `halatuju_api/apps/courses/exam_questions.py` (`QUALIFICATIONS`, `THIRD_ROUTE`,
 * `QUALIFICATION_LABELS`), and a code spelled differently on the two sides is a student silently
 * read as SPM — the failure the roadmap's risk list names for this route. So the copies are pinned
 * against the source here, both ways.
 */
import {
  THIRD_ROUTE, asQualification, completedQualificationsFor, isTertiary, isThirdRoute,
  resultsEditPath,
} from '@/lib/qualification'
import { levelOf } from '@/lib/sponsorFilter'
import { pySeq, readApi } from '@/test/apiSource'

const src = readApi('apps/courses/exam_questions.py')
const apiThird = pySeq(src, 'THIRD_ROUTE')
const apiAll = pySeq(src, 'QUALIFICATIONS')
/** `QUALIFICATION_LABELS` — a dict literal: `'code': 'Label'` pairs. */
const apiLabels = (() => {
  const m = src.match(/^QUALIFICATION_LABELS = \{([\s\S]*?)\}/m)
  if (!m) throw new Error('drift test: QUALIFICATION_LABELS has moved out of exam_questions.py')
  return Object.fromEntries([...m[1].matchAll(/'([a-z]+)':\s*'([^']+)'/g)].map((x) => [x[1], x[2]]))
})()

describe('parse sanity — the server lists were really found', () => {
  test('three third-route codes, five in all, five labels', () => {
    expect(apiThird).toHaveLength(3)
    expect(apiAll).toHaveLength(5)
    expect(Object.keys(apiLabels)).toHaveLength(5)
  })
})

describe('the web vocabulary is the server vocabulary', () => {
  test('THIRD_ROUTE: same codes, same order', () => {
    expect([...THIRD_ROUTE]).toEqual(apiThird)
  })

  test('every server qualification is understood, none is read as SPM by accident', () => {
    for (const q of apiAll) expect(asQualification(q)).toBe(q)
    expect(apiAll.filter((q) => isTertiary(q))).toEqual(['stpm', ...apiThird])
  })

  test("the sponsor filter knows every name the server's card line starts with", () => {
    for (const [code, label] of Object.entries(apiLabels)) {
      expect(levelOf(`${label} · CGPA 3.47`)).toBe(code === 'spm' ? 'SPM' : code === 'stpm' ? 'STPM' : label)
    }
  })
})

describe('the rules the browser owns', () => {
  test('tertiary = STPM + the third route; SPM, blank and unknown are not', () => {
    expect(['stpm', 'matric', 'asasi', 'diploma'].every(isTertiary)).toBe(true)
    expect(['spm', '', 'phd', undefined, null].some(isTertiary)).toBe(false)
    expect(isThirdRoute('stpm')).toBe(false)
  })

  test('an unknown or blank code reads as SPM', () => {
    expect(asQualification('')).toBe('spm')
    expect(asQualification('phd')).toBe('spm')
    expect(asQualification(' Matric ')).toBe('matric')
  })

  test('the completed list is what the last form completed — never a running union (#15)', () => {
    expect(completedQualificationsFor('spm')).toEqual(['spm'])
    expect(completedQualificationsFor('stpm')).toEqual(['spm', 'stpm'])
    expect(completedQualificationsFor('matric')).toEqual(['spm', 'matric'])
    expect(completedQualificationsFor('diploma')).toEqual(['spm', 'diploma'])
    expect(completedQualificationsFor('')).toEqual([])
    expect(completedQualificationsFor('phd')).toEqual([])
  })

  test('each route edits its results on its own form', () => {
    expect(resultsEditPath('spm')).toBe('/onboarding/grades')
    expect(resultsEditPath('stpm')).toBe('/onboarding/stpm-grades')
    expect(resultsEditPath('asasi')).toBe('/onboarding/higher-grades')
    expect(resultsEditPath(undefined)).toBe('/onboarding/grades')
  })
})
