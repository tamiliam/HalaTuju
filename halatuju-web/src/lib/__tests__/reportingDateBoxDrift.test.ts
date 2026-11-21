/**
 * THE DRIFT TEST for `showsReportingDateBox` (F3, I-12). The server refuses a Recommend while the box
 * shows and no date is saved (`course_start.recommend_needs_date`), so the box and the refusal must be
 * one condition. Both sides run the same case table: `tests/reporting_date_box_cases.json`, answered
 * by `course_start.box_shows` in pytest (`test_f3_assessment.py`) and by the web rule here.
 *
 * F3 review fix 1: the cockpit now reads the SERVER's answer (`shows_reporting_date_box`, via
 * `reportingDateBoxShown`). `letter_cases` are whole cases (the letter's date TEXT, a recorded date);
 * pytest checks the server answers them, and here the web follows the served value, even where its
 * own fallback would read "JULAI 2026" as a date.
 */
import { reportingDateBoxShown, showsReportingDateBox } from '@/lib/cockpitTrail'
import { readApi } from '@/test/apiSource'

type Case = { status: string; reopened: boolean; letter_has_date: boolean; shows: boolean }
type LetterCase = {
  status: string; reopened: boolean; letter_date: string | null; recorded: boolean
  letter_has_date: boolean; shows: boolean
}
const { cases, letter_cases: letterCases } = JSON.parse(
  readApi('apps/scholarship/tests/reporting_date_box_cases.json')) as { cases: Case[]; letter_cases: LetterCase[] }

const docsFor = (c: LetterCase) => (c.letter_date === null ? [] : [
  { doc_type: 'offer_letter', superseded_at: null, pathway_check: { reporting_date: c.letter_date } }])

describe('reporting-date box drift (F3)', () => {
  it('the table is not empty and covers both answers', () => {
    expect(cases.length).toBeGreaterThanOrEqual(8)
    expect(cases.some((c) => c.shows)).toBe(true)
    expect(cases.some((c) => !c.shows)).toBe(true)
  })

  it.each(cases)('%o', (c) => {
    expect(showsReportingDateBox({ status: c.status, decisionReopened: c.reopened, letterHasDate: c.letter_has_date }))
      .toBe(c.shows)
  })

  it('the server rule reads the same three inputs', () => {
    const src = readApi('apps/scholarship/course_start.py')
    expect(src).toContain("return (status or '') == 'interviewing' or bool(decision_reopened)")
    expect(src).toContain('if letter_has_date:\n        return False')
  })

  it('the letter table carries the unreadable "JULAI 2026" letter', () => {
    expect(letterCases.some((c) => c.letter_date === 'JULAI 2026' && c.shows)).toBe(true)
  })

  it.each(letterCases)('the cockpit follows the served answer: %o', (c) => {
    expect(reportingDateBoxShown(
      { status: c.status, shows_reporting_date_box: c.shows, documents: docsFor(c) }, c.reopened)).toBe(c.shows)
  })

  it('an unreadable letter date still shows the box when the server says so', () => {
    // The web's own fallback would take the raw text as a date; the served answer wins.
    const app = { status: 'interviewing', shows_reporting_date_box: true,
      documents: [{ doc_type: 'offer_letter', superseded_at: null, pathway_check: { reporting_date: 'JULAI 2026' } }] }
    expect(reportingDateBoxShown({ ...app, shows_reporting_date_box: undefined }, false)).toBe(false)
    expect(reportingDateBoxShown(app, false)).toBe(true)
  })

  it.each([undefined, null])('a payload without the field (%p) falls back to the web rule', (missing) => {
    for (const c of cases) {
      const documents = c.letter_has_date
        ? [{ doc_type: 'offer_letter', superseded_at: null, pathway_check: { reporting_date: '2026-06-22' } }] : []
      expect(reportingDateBoxShown({ status: c.status, shows_reporting_date_box: missing, documents }, c.reopened))
        .toBe(c.shows)
    }
  })

  it('the detail serializer serves the field', () => {
    expect(readApi('apps/scholarship/serializers_admin/detail_blocks.py'))
      .toContain('return course_start.shows_box(obj)')
  })
})
