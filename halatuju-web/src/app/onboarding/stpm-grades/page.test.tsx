/**
 * @jest-environment jsdom
 *
 * TD-069 — the STPM results page's SPM-prerequisite section survives a logout/login, as the SPM
 * page's has since v2.21.0, and its elective slots stop at MAX_SPM_ELECTIVES rather than 2.
 *
 * Why a MOUNT and not a source-shape guard: every claim here is about state after mount or after a
 * click — what the form rebuilds from storage, how many slots a click can add, what a dropdown
 * offers. A guard reading the source would pass while the rebuild ran in the wrong order.
 *
 * The login test mounts the REAL AuthProvider (supabase + the profile fetch mocked), so the
 * hydrate it pins is the one every route runs — not a copy of it.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import StpmGradesPage from './page'
import { AuthProvider } from '@/lib/auth-context'
import { MAX_SPM_ELECTIVES } from '@/lib/subjects'
import {
  KEY_ALIRAN, KEY_ELEKTIF, KEY_GRADES, KEY_MUET_BAND, KEY_SPM_ALIRAN, KEY_SPM_ELEKTIF,
  KEY_SPM_PREREQ, KEY_SPM_STREAM, KEY_STPM_GRADES, KEY_STPM_STREAM,
} from '@/lib/storage'

const push = jest.fn()
let mockProfile: Record<string, unknown> = {}

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace: jest.fn() }),
  usePathname: () => '/onboarding/stpm-grades',
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/api', () => ({
  calculateCgpa: jest.fn().mockResolvedValue({ academic_cgpa: 3.5, cgpa: 3.6 }),
  getProfile: jest.fn(() => Promise.resolve(mockProfile)),
}))
jest.mock('@/lib/supabase', () => ({
  getSession: () => Promise.resolve({
    session: { access_token: 'tkn', user: { is_anonymous: false } },
  }),
  signInAnonymously: jest.fn(),
  getSupabase: () => ({
    auth: { onAuthStateChange: () => ({ data: { subscription: { unsubscribe: jest.fn() } } }) },
  }),
}))
jest.mock('@/components/BrandLogo', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/ProgressStepper', () => ({ __esModule: true, default: () => null }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const CORE = { bm: 'A', eng: 'A', hist: 'B+', math: 'A' }
const PREREQ = { ...CORE, phy: 'A', chem: 'B', ekonomi: 'A-', poa: 'B+', geo: 'A' }
const ELECTIVES = ['ekonomi', 'poa', 'geo']

/**
 * The value of every SPM-prerequisite subject dropdown, in render order: the four aliran rows,
 * then one per elective slot. ⚠ The VALUES are the claim — a dropdown whose chosen subject is not
 * among its own options shows the placeholder (jsdom resets it to ''), which is how the elective
 * self-exclusion bug below was seen at all.
 */
const spmSubjectValues = () =>
  screen
    .queryAllByText('onboarding.selectSubject')
    .map((option) => (option.closest('select') as HTMLSelectElement).value)

const optionsOf = (select: HTMLSelectElement) =>
  Array.from(select.options).map((o) => o.value).filter(Boolean)

beforeEach(() => {
  localStorage.clear()
  push.mockClear()
  mockProfile = {}
})

describe('the SPM-prerequisite section rebuilds from the durable record', () => {
  it('rebuilds aliran AND electives from grades + electives alone (no aliran key)', () => {
    // Exactly what a fresh browser holds after the login hydrate: no KEY_SPM_ALIRAN, because the
    // server does not store it — the form derives it (grades minus the core minus the electives).
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(PREREQ))
    localStorage.setItem(KEY_SPM_ELEKTIF, JSON.stringify(ELECTIVES))
    localStorage.setItem(KEY_SPM_STREAM, 'science')
    render(<StpmGradesPage />)

    expect(spmSubjectValues()).toEqual(['phy', 'chem', '', '', 'ekonomi', 'poa', 'geo'])
  })

  it('prefers a saved aliran pick over the derivation (this browser saved it itself)', () => {
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(PREREQ))
    localStorage.setItem(KEY_SPM_ELEKTIF, JSON.stringify(ELECTIVES))
    localStorage.setItem(KEY_SPM_ALIRAN, JSON.stringify(['chem', 'bio']))
    render(<StpmGradesPage />)

    expect(spmSubjectValues().slice(0, 4)).toEqual(['chem', 'bio', '', ''])
  })

  it('saves under the shared storage keys, which the profile sync reads', async () => {
    localStorage.setItem(KEY_STPM_STREAM, 'science')
    localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A', MATH_T: 'A', PHYSICS: 'A', CHEMISTRY: 'B' }))
    localStorage.setItem(KEY_MUET_BAND, '4')
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(PREREQ))
    localStorage.setItem(KEY_SPM_ELEKTIF, JSON.stringify(ELECTIVES))
    localStorage.setItem(KEY_SPM_STREAM, 'science')
    render(<StpmGradesPage />)

    fireEvent.click(screen.getByText('common.continue'))

    await waitFor(() => expect(push).toHaveBeenCalledWith('/onboarding/profile'))
    expect(JSON.parse(localStorage.getItem(KEY_SPM_ELEKTIF) as string)).toEqual(ELECTIVES)
    expect(JSON.parse(localStorage.getItem(KEY_SPM_ALIRAN) as string)).toEqual(['phy', 'chem'])
    expect(JSON.parse(localStorage.getItem(KEY_SPM_PREREQ) as string)).toEqual(PREREQ)
  })
})

describe('the elective slots', () => {
  it(`stop at MAX_SPM_ELECTIVES (${MAX_SPM_ELECTIVES}), not 2`, () => {
    render(<StpmGradesPage />)
    let added = 0
    while (screen.queryByText('onboarding.spmAddElective') && added < 20) {
      fireEvent.click(screen.getByText('onboarding.spmAddElective'))
      added++
    }
    expect(added).toBe(MAX_SPM_ELECTIVES)
    expect(spmSubjectValues()).toHaveLength(4 + MAX_SPM_ELECTIVES)
  })

  it('offer each slot its own pick, and never a subject picked anywhere else', () => {
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(PREREQ))
    localStorage.setItem(KEY_SPM_ELEKTIF, JSON.stringify(ELECTIVES))
    localStorage.setItem(KEY_SPM_STREAM, 'science')
    render(<StpmGradesPage />)

    const selects = screen
      .queryAllByText('onboarding.selectSubject')
      .map((o) => o.closest('select') as HTMLSelectElement)
    const firstElective = optionsOf(selects[4])
    // its own pick is offered, so the row can show it…
    expect(firstElective).toContain('ekonomi')
    // …and nothing picked in another slot, an aliran row, or the core.
    for (const taken of ['poa', 'geo', 'phy', 'chem', 'bm', 'eng', 'hist', 'math']) {
      expect(firstElective).not.toContain(taken)
    }
    // positive control: the list is not simply empty
    expect(firstElective.length).toBeGreaterThan(10)
  })
})

describe('a simulated login restores the record (the real AuthProvider hydrate)', () => {
  it('re-hydrates the STPM path and leaves the SPM path hydrate as it was', async () => {
    mockProfile = {
      nric: '900101-01-1234',
      exam_type: 'stpm',
      grades: { bm: 'A', eng: 'A' },
      stream_subjects: ['phy', 'chem'],
      elective_subjects: ['ekonomi'],
      spm_prereq_grades: PREREQ,
      spm_elective_subjects: ELECTIVES,
      spm_stream: 'technical',
    }
    const { unmount } = render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(localStorage.getItem(KEY_SPM_ELEKTIF)).not.toBeNull())

    expect(JSON.parse(localStorage.getItem(KEY_SPM_PREREQ) as string)).toEqual(PREREQ)
    expect(JSON.parse(localStorage.getItem(KEY_SPM_ELEKTIF) as string)).toEqual(ELECTIVES)
    expect(localStorage.getItem(KEY_SPM_STREAM)).toBe('technical')
    // (c) the main SPM flow's hydrate is untouched — same keys, same values as before TD-069.
    expect(JSON.parse(localStorage.getItem(KEY_GRADES) as string)).toEqual({ bm: 'A', eng: 'A' })
    expect(JSON.parse(localStorage.getItem(KEY_ALIRAN) as string)).toEqual(['phy', 'chem'])
    expect(JSON.parse(localStorage.getItem(KEY_ELEKTIF) as string)).toEqual(['ekonomi'])
    // the two paths keep separate keys — the STPM electives never land in the SPM path's slot
    expect(KEY_SPM_ELEKTIF).not.toBe(KEY_ELEKTIF)
    unmount()

    // …and the page the student returns to rebuilds the whole section from that.
    render(<StpmGradesPage />)
    expect(spmSubjectValues()).toEqual(['phy', 'chem', '', '', 'ekonomi', 'poa', 'geo'])
  })

  it("drops this browser's aliran picks when it writes the server's grades (review F2)", async () => {
    // Device B saved aliran ['bio'] earlier; the server's grades are device A's. Keeping B's aliran
    // beside A's grades would draw a mixed form — so the hydrate removes it and the form
    // re-derives the aliran from the grades it was given.
    localStorage.setItem(KEY_SPM_ALIRAN, JSON.stringify(['bio']))
    mockProfile = {
      nric: '900101-01-1234', exam_type: 'stpm',
      spm_prereq_grades: PREREQ, spm_elective_subjects: ELECTIVES, spm_stream: 'science',
    }
    const { unmount } = render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(localStorage.getItem(KEY_SPM_PREREQ)).not.toBeNull())
    expect(localStorage.getItem(KEY_SPM_ALIRAN)).toBeNull()
    unmount()
    render(<StpmGradesPage />)
    expect(spmSubjectValues().slice(0, 4)).toEqual(['phy', 'chem', '', ''])
  })

  it('writes nothing for a profile that never entered SPM prerequisites', async () => {
    mockProfile = { nric: '900101-01-1234', exam_type: 'spm', grades: { bm: 'A' } }
    render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(localStorage.getItem(KEY_GRADES)).not.toBeNull())

    expect(localStorage.getItem(KEY_SPM_PREREQ)).toBeNull()
    expect(localStorage.getItem(KEY_SPM_ELEKTIF)).toBeNull()
    expect(localStorage.getItem(KEY_SPM_STREAM)).toBeNull()
  })
})
