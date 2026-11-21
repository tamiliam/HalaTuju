/**
 * THE DRIFT TEST for `showsReportingDateBox` (F3, I-12). The server refuses a Recommend while the box
 * shows and no date is saved (`course_start.recommend_needs_date`), so the box and the refusal must be
 * one condition. Both sides run the same case table: `tests/reporting_date_box_cases.json`, answered
 * by `course_start.box_shows` in pytest (`test_f3_assessment.py`) and by the web rule here.
 */
import { showsReportingDateBox } from '@/lib/cockpitTrail'
import { readApi } from '@/test/apiSource'

type Case = { status: string; reopened: boolean; letter_has_date: boolean; shows: boolean }
const { cases } = JSON.parse(readApi('apps/scholarship/tests/reporting_date_box_cases.json')) as { cases: Case[] }

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
})
