/**
 * @jest-environment jsdom
 *
 * The school list loads on demand (TD-352, 2026-10-06).
 *
 * The facts the lazy load must not change, and the saving it exists for:
 *   1. a value typed BEFORE the list arrives is kept — the typed text is the value, always;
 *   2. suggestions appear once the list resolves, and picking one fills the official name;
 *   3. pointer-over starts the load (so a fast typist rarely waits), as focus does;
 *   4. a failed load only means no suggestions — the sibling `SchoolSelect.failure.test.tsx`;
 *   5. none of the three routes that draw the field imports the list statically, and the field
 *      itself takes only a TYPE from it. Jest cannot measure kilobytes (`npm run bundle-budget`
 *      does), so this pins the import lines.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { readWeb } from '@/test/sourceGuard'
import SchoolSelect from './SchoolSelect'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/data/secondary-schools', () => ({
  searchSchools: (q: string) => (q.trim().length < 2 ? [] : [
    { code: 'A1', name: 'SMK TAMAN SEA', state: 'Selangor', type: 'SMK' },
    { code: 'A2', name: 'SMK TAMAN MELAWATI', state: 'Kuala Lumpur', type: 'SMK' },
  ].filter((s) => s.name.toLowerCase().includes(q.trim().toLowerCase()))),
}))

const submitted: string[] = []

function Field() {
  const [school, setSchool] = useState('')
  submitted.push(school)
  return <SchoolSelect value={school} onChange={setSchool} />
}

const box = () => screen.getByRole('combobox') as HTMLInputElement

beforeEach(() => { submitted.length = 0 })

it('keeps what was typed before the list arrives, then suggests once it does', async () => {
  render(<Field />)
  fireEvent.focus(box())
  fireEvent.change(box(), { target: { value: 'smk taman' } })   // before the import resolves
  expect(box().value).toBe('smk taman')
  expect(screen.queryByRole('option')).toBeNull()                // nothing yet, and no "no match"
  expect(screen.queryByText('scholarship.apply.schoolNoMatch')).toBeNull()

  expect(await screen.findAllByRole('option')).toHaveLength(2)    // the list landed
  expect(box().value).toBe('smk taman')                          // still what she typed
  expect(submitted[submitted.length - 1]).toBe('smk taman')

  fireEvent.click(screen.getByText('SMK TAMAN MELAWATI'))
  expect(box().value).toBe('SMK TAMAN MELAWATI')
})

it('starts the load on pointer-over, before any focus', async () => {
  render(<Field />)
  fireEvent.pointerEnter(box())
  await act(async () => { await Promise.resolve() })
  fireEvent.focus(box())
  fireEvent.change(box(), { target: { value: 'sea' } })
  // Already loaded: the suggestion is there in the same render, no wait.
  expect(screen.getAllByRole('option')).toHaveLength(1)
})

describe('the saving is the import line', () => {
  it('the field takes only a TYPE from the list and owns a LITERAL import()', () => {
    const field = readWeb('src/components/SchoolSelect.tsx', 'the school field')
    expect(field).toContain("import('@/data/secondary-schools')")
    expect(field).toMatch(/^import type \{ SecondarySchool \} from '@\/data\/secondary-schools'$/m)
    expect(field).not.toMatch(/^import (?!type)[^\n]*'@\/data\/secondary-schools'/m)
  })

  it.each([
    'src/app/scholarship/apply/page.tsx',
    'src/app/profile/page.tsx',
    'src/app/onboarding/profile/page.tsx',
  ])('%s does not import the list statically', (route) => {
    const page = readWeb(route, 'a route that draws the school field')
    expect(page).toContain("from '@/components/SchoolSelect'")
    expect(page).not.toMatch(/from\s+'@\/data\/secondary-schools'/)
  })
})
