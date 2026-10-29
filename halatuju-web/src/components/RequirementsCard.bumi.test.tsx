/**
 * @jest-environment jsdom
 *
 * Bumi coverage Sprint D1 — an SPM course page for a Bumiputera-only (UiTM) course shows the course
 * (no 404) with a "Bumiputera only" row, like the STPM page, and shows the new count-once
 * requirements ("N more subjects not already counted") instead of dropping them.
 */
import { render, screen } from '@testing-library/react'

import RequirementsCard, { type CourseRequirements } from './RequirementsCard'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) => (p ? `${k}(${Object.values(p).join(',')})` : k),
    locale: 'en',
  }),
}))

// DIPLOMA KEJURURAWATAN (UE4723001), as `CourseRequirementSerializer` serves it.
const UITM: CourseRequirements = {
  source_type: 'ua', req_bumiputera: true,
  general: [{ key: 'req_malaysian', label: 'Warganegara Malaysia' },
            { key: 'req_bumiputera', label: 'Bumiputera sahaja' }],
  special: [{ key: 'credit_english', label: 'Kredit Bahasa Inggeris' }],
  complex_requirements: {
    count_once: [
      { groups: [], remaining: [{ count: 2, grade: 'C', exclude: [] }] },
      { groups: [{ count: 1, grade: 'C', subjects: ['math', 'addmath'] }],
        remaining: [{ count: 1, grade: 'C', exclude: ['eng'] }] },
    ],
  },
  subject_group_req: null, merit_cutoff: 84.72, remarks: '',
}

it('shows the Bumiputera-only row in the general requirements', () => {
  render(<RequirementsCard requirements={UITM} />)
  expect(screen.getByText('courseDetail.bumiputeraOnly')).toBeTruthy()
  expect(screen.queryByText('Bumiputera sahaja')).toBeNull()
})

it('shows the count-once groups and the "more subjects" lines', () => {
  const { container } = render(<RequirementsCard requirements={UITM} />)
  expect(container.textContent).toContain('courseDetail.otherSubjects(C,2)')
  expect(container.textContent).toContain('courseDetail.otherSubjects(C,1) courseDetail.exceptSubjects')
  expect(screen.getAllByText(/Mathematics|Matematik/).length).toBeGreaterThan(0)
})

it('an open course shows no Bumiputera row', () => {
  render(<RequirementsCard requirements={{ ...UITM, req_bumiputera: false, general: UITM.general.slice(0, 1) }} />)
  expect(screen.queryByText('courseDetail.bumiputeraOnly')).toBeNull()
})
