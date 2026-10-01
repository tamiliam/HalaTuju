/**
 * @jest-environment jsdom
 *
 * TD-313 — a TVET course page never prints a raw requirement-type name.
 *
 * The TVET list draws "label · value" rows, and the label came from `tvetKeyLabel`, which knows
 * only the eight GENERAL keys; every SPECIAL key (39 in the api's `SPECIAL_FIELDS` plus
 * `req_interview`) fell back to the raw field name, so a row read "credit_bmbi · Kredit BM atau
 * BI". The lead's choice (no 120 new strings): a special key's row shows ONLY the served Malay
 * label, as the non-TVET list does. Trilingual labels for the special keys remain open.
 *
 * The sample below is the reviewer's kind of key (composite OR-groups, TVET composites, grade B,
 * distinction) plus `req_interview`, in all three locales.
 */
import { render, screen } from '@testing-library/react'

import RequirementsCard, { type CourseRequirements } from './RequirementsCard'

let mockLocale = 'en'
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: mockLocale }) }))

/** Served exactly as `CourseRequirementSerializer` serves them: the key and its Malay label. */
const SPECIAL = [
  { key: 'credit_math_or_addmath', label: 'Kredit Matematik atau Matematik Tambahan' },
  { key: 'pass_science_tech', label: 'Lulus Sains atau subjek Teknikal' },
  { key: 'credit_bmbi', label: 'Kredit BM atau BI' },
  { key: 'credit_math_b', label: 'Gred B+ Matematik' },
  { key: 'distinction_phy', label: 'Cemerlang (A-) Fizik' },
  { key: 'three_m_only', label: 'Boleh membaca, menulis dan mengira (3M)' },
  { key: 'req_interview', label: 'Temuduga diperlukan' },
]
const GENERAL = [
  { key: 'req_malaysian', label: 'Warganegara Malaysia' },
  { key: 'min_credits', label: 'Minimum 3 kredit', value: 3 },
  { key: 'req_male', label: 'Lelaki sahaja' },
]

const tvet = (over: Partial<CourseRequirements> = {}): CourseRequirements => ({
  source_type: 'tvet', general: GENERAL, special: SPECIAL, complex_requirements: null,
  subject_group_req: null, merit_cutoff: null, remarks: '', ...over,
})

describe.each(['en', 'ms', 'ta'])('TD-313 in %s', (locale) => {
  beforeEach(() => { mockLocale = locale })

  it('no raw key appears anywhere on the card', () => {
    const { container } = render(<RequirementsCard requirements={tvet()} />)
    for (const { key } of [...SPECIAL, ...GENERAL]) {
      expect(container.textContent).not.toContain(key)
    }
  })

  it('each special requirement shows its served Malay label, once, on its own', () => {
    render(<RequirementsCard requirements={tvet()} />)
    for (const { label } of SPECIAL) {
      const node = screen.getByText(label)
      expect(node.parentElement?.textContent).toBe(label)   // nothing beside it on the row
    }
  })
})

describe('the eight general keys keep their label · value rows', () => {
  it('in English', () => {
    mockLocale = 'en'
    render(<RequirementsCard requirements={tvet({ special: [] })} />)
    expect(screen.getByText('Nationality')).toBeTruthy()
    expect(screen.getByText('Malaysian')).toBeTruthy()
    expect(screen.getByText('Minimum Credits')).toBeTruthy()
    expect(screen.getByText('Min. 3')).toBeTruthy()
    expect(screen.getByText('Gender')).toBeTruthy()
    expect(screen.getByText('Male Only')).toBeTruthy()
  })

  it('in Malay (the label Tamil readers see too)', () => {
    mockLocale = 'ms'
    render(<RequirementsCard requirements={tvet({ special: [] })} />)
    expect(screen.getByText('Warganegara')).toBeTruthy()
    expect(screen.getByText('Kredit Minimum')).toBeTruthy()
    expect(screen.getByText('Lelaki Sahaja')).toBeTruthy()
  })

  it('an unknown key in the GENERAL list is handled the same way — its label, never the key', () => {
    mockLocale = 'en'
    const { container } = render(<RequirementsCard requirements={tvet({
      general: [{ key: 'some_future_flag', label: 'Syarat baharu' }], special: [] })} />)
    expect(container.textContent).not.toContain('some_future_flag')
    expect(screen.getByText('Syarat baharu')).toBeTruthy()
  })
})
