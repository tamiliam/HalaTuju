/**
 * @jest-environment jsdom
 *
 * Bumi coverage Sprint D2 (review round 1, H1): a count-once group may be an `any_of` (MOHE "ATAU")
 * with no `subjects` of its own. The course page read `group.subjects.length` and crashed on every
 * such row. These are the REAL requirement shapes from the D2 review file, read as the API serves them.
 */
import fs from 'fs'
import path from 'path'
import { fireEvent, render, screen } from '@testing-library/react'

import RequirementsCard from '@/components/RequirementsCard'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))

const D2 = path.join(__dirname, '..', '..', '..', 'halatuju_api', 'data', 'spm', 'spm_new_courses_D2.json')
const rows: Record<string, { requirement: { complex_requirements: unknown } }> = Object.fromEntries(
  JSON.parse(fs.readFileSync(D2, 'utf-8')).courses.map((c: { course_id: string }) => [c.course_id, c]),
)
// Long lists start folded at three groups; open every fold, as a student would.
const mount = (id: string) => {
  render(<RequirementsCard requirements={card(id) as never} />)
  screen.queryAllByRole('button').forEach((b) => fireEvent.click(b))
}
const card = (id: string) => ({
  source_type: 'ua', general: [], special: [], subject_group_req: null, merit_cutoff: null, remarks: '',
  complex_requirements: rows[id].requirement.complex_requirements,
})

it.each(['UQ0010002', 'UY0000007', 'UY0000004', 'UM0221002', 'UE4811004'])(
  '%s renders its ATAU as "one of" with every alternative', (id) => {
    mount(id)
    expect(screen.getAllByText('courseDetail.oneOf').length).toBeGreaterThan(0)
    expect(screen.getAllByText('courseDetail.orAlternative').length).toBeGreaterThan(0)
  })

it('UY0000007 shows both alternatives: A- English, or B+ English with an Arabic subject', () => {
  mount('UY0000007')
  expect(screen.getAllByText('English').length).toBe(2)
  expect(screen.getByText('courseDetail.orAlternative')).toBeTruthy()
})
