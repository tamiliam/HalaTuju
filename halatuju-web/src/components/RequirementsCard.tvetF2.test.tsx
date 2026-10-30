/**
 * @jest-environment jsdom
 *
 * Bumi coverage Sprint F2 — every MARA course in the reviewed file renders on the course page (lesson: a
 * new shape in a shared JSON field is a change to EVERY reader). These are the REAL rows of
 * `halatuju_api/data/tvet/tvet_new_courses_F2.json` (GIATMARA, IKM, KKTM, MJII), served the way
 * `CourseRequirementSerializer` serves them: pathway "mara", an open row with nothing but its remarks,
 * and the KKTM diplomas whose remark carries the page's own heading (the remedial-Maths note).
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
  requirement: {
    complex_requirements: CourseRequirements['complex_requirements']
    remarks: string
    req_bumiputera: boolean
  }
}
const F2 = path.join(__dirname, '..', '..', '..', 'halatuju_api', 'data', 'tvet', 'tvet_new_courses_F2.json')
const rows: Row[] = JSON.parse(fs.readFileSync(F2, 'utf-8')).courses

const served = (row: Row, over: Partial<CourseRequirements> = {}): CourseRequirements => ({
  source_type: 'tvet', pathway_type: 'mara', general: [], special: [], subject_group_req: null,
  merit_cutoff: null, complex_requirements: row.requirement.complex_requirements,
  remarks: row.requirement.remarks, ...over,
})

it('the file is all MARA, holds open rows and rows with a subject rule, Bumi-only and not', () => {
  expect(rows.length).toBeGreaterThan(100)
  expect(rows.every((r) => r.family === 'mara')).toBe(true)
  expect(rows.some((r) => !r.requirement.complex_requirements)).toBe(true)
  expect(rows.some((r) => r.requirement.complex_requirements)).toBe(true)
  expect(rows.some((r) => !r.requirement.req_bumiputera)).toBe(true)
})

it.each(rows.map((r) => [r.course_id, r] as const))('%s renders, with its remarks and the MARA chip', (_id, row) => {
  render(<RequirementsCard requirements={served(row)} />)
  screen.queryAllByRole('button').forEach((b) => fireEvent.click(b))
  expect(screen.getByText(row.requirement.remarks)).toBeTruthy()
  expect(screen.getByText('MARA')).toBeTruthy()
})

it('every subject a MARA rule names has a display name (no humanised engine key)', () => {
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
  expect(keys.size).toBeGreaterThan(20)
  expect([...keys].filter((k) => !SUBJECT_NAMES[k])).toEqual([])
})

it('the remedial-Maths heading reaches the student as text', () => {
  const kktm = rows.find((r) => r.requirement.remarks.includes('Program Remedial Matematik'))!
  render(<RequirementsCard requirements={served(kktm)} />)
  expect(screen.getByText(kktm.requirement.remarks)).toBeTruthy()
})
