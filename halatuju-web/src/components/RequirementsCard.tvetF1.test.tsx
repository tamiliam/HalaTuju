/**
 * @jest-environment jsdom
 *
 * Bumi coverage Sprint F1 — every new UP_TVET course in the reviewed file renders on the course page
 * (lesson: a new shape in a shared JSON field is a change to EVERY reader). These are the REAL rows of
 * `halatuju_api/data/tvet/tvet_new_courses_F1.json`, served the way `CourseRequirementSerializer`
 * serves them: an open row may carry nothing but its remarks (age, health), and that text must still
 * show; the chip is the row's PATHWAY (ILJTM / ILKBS / MARA / "Latihan Kemahiran").
 */
import fs from 'fs'
import path from 'path'
import { fireEvent, render, screen } from '@testing-library/react'

import RequirementsCard, { type CourseRequirements } from '@/components/RequirementsCard'
import { SUBJECT_NAMES } from '@/lib/subjects'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))

interface Row {
  course_id: string
  family: string
  requirement: { complex_requirements: CourseRequirements['complex_requirements']; remarks: string }
}
const F1 = path.join(__dirname, '..', '..', '..', 'halatuju_api', 'data', 'tvet', 'tvet_new_courses_F1.json')
const rows: Row[] = JSON.parse(fs.readFileSync(F1, 'utf-8')).courses
const PATHWAY: Record<string, string> = { iljtm: 'iljtm', ilkbs: 'ilkbs', mara: 'mara' }
const pathwayOf = (row: Row) => PATHWAY[row.family] || 'tvet_other'

const served = (row: Row, over: Partial<CourseRequirements> = {}): CourseRequirements => ({
  source_type: 'tvet', pathway_type: pathwayOf(row), general: [], special: [], subject_group_req: null,
  merit_cutoff: null, complex_requirements: row.requirement.complex_requirements,
  remarks: row.requirement.remarks, ...over,
})

it('the file holds open rows and rows with a subject rule', () => {
  expect(rows.some((r) => !r.requirement.complex_requirements)).toBe(true)
  expect(rows.some((r) => r.requirement.complex_requirements)).toBe(true)
})

it.each(rows.map((r) => [r.course_id, r] as const))('%s renders, with its remarks', (_id, row) => {
  render(<RequirementsCard requirements={served(row)} />)
  screen.queryAllByRole('button').forEach((b) => fireEvent.click(b))
  expect(screen.getByText(row.requirement.remarks)).toBeTruthy()
})

it('every subject a new rule names has a display name (no humanised engine key)', () => {
  const keys = new Set<string>()
  const walk = (x: unknown): void => {
    if (Array.isArray(x)) { x.forEach(walk); return }
    if (x && typeof x === 'object') {
      for (const [k, v] of Object.entries(x)) {
        if (['subjects', 'exclude', 'counted'].includes(k)) (v as string[]).forEach((s) => keys.add(s))
        else if (k === 'slots') (v as string[][]).flat().forEach((s) => keys.add(s))
        else walk(v)
      }
    }
  }
  rows.forEach((r) => walk(r.requirement.complex_requirements))
  expect([...keys].filter((k) => !SUBJECT_NAMES[k])).toEqual([])
})

it('the chip names the pathway: "Latihan Kemahiran" for the other public bodies, MARA for MARA', () => {
  const other = rows.find((r) => pathwayOf(r) === 'tvet_other')!
  const { unmount } = render(<RequirementsCard requirements={served(other)} />)
  expect(screen.getByText('Latihan Kemahiran')).toBeTruthy()
  unmount()
  render(<RequirementsCard requirements={served(other, { pathway_type: 'mara' })} />)
  expect(screen.getByText('MARA')).toBeTruthy()
})

it('an open row with only its remarks still renders the card', () => {
  const open = rows.find((r) => !r.requirement.complex_requirements)!
  render(<RequirementsCard requirements={served(open)} />)
  expect(screen.getByText('courseDetail.requirements')).toBeTruthy()
})
