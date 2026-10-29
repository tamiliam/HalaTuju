/**
 * @jest-environment jsdom
 *
 * Bumi coverage Sprint D2 (D1 follow-up L4): the search page's pick-lists (levels, states, types)
 * come from the FIRST search response and were never re-loaded. A Bumiputera student's answer
 * arrives after that first search (the profile hydrates), so her pick-lists stayed the non-Bumi
 * ones. A new answer now drops them and the next search re-loads them; a response asked under the
 * OLD answer that lands late is dropped, so it can never put the old lists back.
 *
 * Mounted with the page's own effects; the server, header, footer and cards are stand-ins.
 */
import { act, render, screen, waitFor } from '@testing-library/react'

import SearchPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { searchCourses } from '@/lib/api'
import { KEY_PROFILE } from '@/lib/storage'

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/search',
  useSearchParams: () => new URLSearchParams(),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  searchCourses: jest.fn(),
  checkEligibility: jest.fn(),
  checkStpmEligibility: jest.fn(),
}))
jest.mock('@/hooks/useSavedCourses', () => ({ useSavedCourses: () => ({ savedIds: new Set(), toggleSave: jest.fn() }) }))
jest.mock('@/hooks/useFieldTaxonomy', () => ({ useFieldTaxonomy: () => ({ fieldOptions: [], loaded: false }) }))
jest.mock('@/components/AppHeader', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/AppFooter', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/CourseCard', () => ({ __esModule: true, default: () => null }))
// A pick-list is drawn as its options, so the test can read what the student may pick from.
jest.mock('@/components/FilterPill', () => ({
  __esModule: true,
  default: ({ label, options }: { label: string; options: string[] }) => (
    <ul aria-label={label}>{options.map((o) => <li key={o}>{o}</li>)}</ul>
  ),
}))

const filters = (levels: string[]) => ({ source_types: [], levels, fields: [], states: [], alirans: [] })
const OPEN = { courses: [], total_count: 0, filters: filters(['Diploma']) }
const WITH_BUMI = { courses: [], total_count: 0, filters: filters(['Diploma', 'Pra-U (Bumiputera)']) }
const answer = (bumi: boolean | undefined) => (bumi ? WITH_BUMI : OPEN)

const mount = (profile: Record<string, unknown> | null) => (
  <AuthContext.Provider value={{ status: 'ready', profile, isAuthenticated: false, showAuthGate: () => {} } as never}>
    <SearchPage />
  </AuthContext.Provider>
)

beforeEach(() => {
  localStorage.clear()
  ;(searchCourses as jest.Mock).mockReset()
})

it('re-loads the pick-lists when a Bumiputera answer arrives after the first search', async () => {
  ;(searchCourses as jest.Mock).mockImplementation(({ bumiputera }) => Promise.resolve(answer(bumiputera)))
  const view = render(mount(null))
  await waitFor(() => expect(screen.getByText('Diploma')).toBeTruthy())
  expect(screen.queryByText('Pra-U (Bumiputera)')).toBeNull()

  // The profile hydrates: a Malaysian who said yes.
  localStorage.setItem(KEY_PROFILE, JSON.stringify({ nationality: 'malaysian', bumiputera: true }))
  view.rerender(mount({ nationality: 'malaysian', bumiputera: true }))

  await waitFor(() => expect(screen.getByText('Pra-U (Bumiputera)')).toBeTruthy())
  const calls = (searchCourses as jest.Mock).mock.calls.map(([params]) => params.bumiputera)
  expect(calls[0]).toBeUndefined()
  expect(calls[calls.length - 1]).toBe(true)
})

it('drops a late response asked under the old answer', async () => {
  // The first (non-Bumi) search answers only when the test lets it — after the Bumi one.
  let releaseOld: (v: unknown) => void = () => {}
  ;(searchCourses as jest.Mock).mockImplementation(({ bumiputera }) =>
    bumiputera ? Promise.resolve(WITH_BUMI) : new Promise((resolve) => { releaseOld = resolve }))
  const view = render(mount(null))
  await waitFor(() => expect(searchCourses).toHaveBeenCalled())

  localStorage.setItem(KEY_PROFILE, JSON.stringify({ nationality: 'malaysian', bumiputera: true }))
  view.rerender(mount({ nationality: 'malaysian', bumiputera: true }))
  await waitFor(() => expect(screen.getByText('Pra-U (Bumiputera)')).toBeTruthy())

  await act(async () => { releaseOld(OPEN) })
  expect(screen.getByText('Pra-U (Bumiputera)')).toBeTruthy()
})

it('a foreign student who answered yes keeps the open lists', async () => {
  ;(searchCourses as jest.Mock).mockImplementation(({ bumiputera }) => Promise.resolve(answer(bumiputera)))
  localStorage.setItem(KEY_PROFILE, JSON.stringify({ nationality: 'non_malaysian', bumiputera: true }))
  render(mount({ nationality: 'non_malaysian', bumiputera: true }))
  await waitFor(() => expect(screen.getByText('Diploma')).toBeTruthy())
  expect(screen.queryByText('Pra-U (Bumiputera)')).toBeNull()
  expect((searchCourses as jest.Mock).mock.calls.every(([params]) => params.bumiputera === undefined)).toBe(true)
})
