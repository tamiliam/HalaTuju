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
  KEY_SPM_PREREQ, KEY_SPM_STREAM, KEY_STPM_GRADES, KEY_STPM_STREAM, KEY_KOKO_SCORE, KEY_STPM_CGPA,
} from '@/lib/storage'

const push = jest.fn()
let mockProfile: Record<string, unknown> = {}

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace: jest.fn() }),
  usePathname: () => '/onboarding/stpm-grades',
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
/**
 * The server's calculator (`stpm_pngk.stpm_calculation`), faked by its contract: a PNGK only from
 * PA + three graded subjects, a merit only with a co-curriculum score too.
 */
const mockCalculateCgpa = jest.fn((grades: Record<string, string>, koko: number | null) =>
  Promise.resolve(Object.keys(grades).length < 4
    ? { cgpa: null, counted: [], overall: null, merit_percent: null }
    : { cgpa: 3.75, counted: ['PA', 'MATH_T', 'PHYSICS', 'CHEMISTRY'],
        overall: koko === null ? null : 3.69, merit_percent: koko === null ? null : 92.25 }))
jest.mock('@/lib/api', () => ({
  calculateCgpa: (g: Record<string, string>, k: number | null) => mockCalculateCgpa(g, k),
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
  mockCalculateCgpa.mockClear()
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
    localStorage.setItem(KEY_KOKO_SCORE, '8')
    render(<StpmGradesPage />)

    const button = screen.getByText('common.continue').closest('button') as HTMLButtonElement
    await waitFor(() => expect(button.disabled).toBe(false))      // the server's PNGK has arrived
    fireEvent.click(button)

    await waitFor(() => expect(push).toHaveBeenCalledWith('/onboarding/profile'))
    expect(JSON.parse(localStorage.getItem(KEY_SPM_ELEKTIF) as string)).toEqual(ELECTIVES)
    expect(JSON.parse(localStorage.getItem(KEY_SPM_ALIRAN) as string)).toEqual(['phy', 'chem'])
    expect(JSON.parse(localStorage.getItem(KEY_SPM_PREREQ) as string)).toEqual(PREREQ)
    // STPM CGPA sprint C2: the PNGK (never a typed or plain-average figure) and the koko score
    expect(localStorage.getItem(KEY_STPM_CGPA)).toBe('3.75')
    expect(localStorage.getItem(KEY_KOKO_SCORE)).toBe('8')
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

// ── Third results route S2b, ruling D4: the SPM block is REQUIRED on the STPM page too ─────────
describe('D4 — Continue waits for the SPM results block', () => {
  const stpmReady = () => {
    localStorage.setItem(KEY_STPM_STREAM, 'science')
    localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A', MATH_T: 'A', PHYSICS: 'A', CHEMISTRY: 'B' }))
    localStorage.setItem(KEY_MUET_BAND, '4')
    localStorage.setItem(KEY_KOKO_SCORE, '8')
  }
  const continueButton = () => screen.getByText('common.continue').closest('button') as HTMLButtonElement

  it('is disabled with STPM complete but the four compulsory SPM subjects not all graded', () => {
    stpmReady()
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify({ bm: 'A', eng: 'A', hist: 'B' }))   // no math
    render(<StpmGradesPage />)
    expect(continueButton().disabled).toBe(true)
    fireEvent.click(continueButton())
    expect(push).not.toHaveBeenCalled()
  })

  it('opens once the last compulsory SPM grade is chosen — on the shared block', async () => {
    stpmReady()
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify({ bm: 'A', eng: 'A', hist: 'B' }))
    render(<StpmGradesPage />)
    const mathRow = screen.getByText('Matematik').parentElement as HTMLElement
    fireEvent.change(mathRow.querySelector('select') as HTMLSelectElement, { target: { value: 'B+' } })
    await waitFor(() => expect(continueButton().disabled).toBe(false))
    fireEvent.click(continueButton())
    await waitFor(() => expect(push).toHaveBeenCalledWith('/onboarding/profile'))
    expect(JSON.parse(localStorage.getItem(KEY_SPM_PREREQ) as string)).toMatchObject({ math: 'B+' })
  })

  it('is disabled with no SPM block at all (it used to be optional)', () => {
    stpmReady()
    render(<StpmGradesPage />)
    expect(continueButton().disabled).toBe(true)
  })
})

// ── S2b review (D4 prefill): the compulsory SPM grades already in `grades` fill the block ─────────
describe('the required SPM block prefills from the SPM grades on file', () => {
  it('fills the four compulsory subjects from KEY_GRADES when the block holds none, so Continue opens', async () => {
    localStorage.setItem(KEY_STPM_STREAM, 'science')
    localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A', MATH_T: 'A', PHYSICS: 'A', CHEMISTRY: 'B' }))
    localStorage.setItem(KEY_MUET_BAND, '4')
    localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A', eng: 'B+', hist: 'B', math: 'A-', moral: 'A' }))
    localStorage.setItem(KEY_KOKO_SCORE, '8')
    render(<StpmGradesPage />)
    const mathRow = screen.getByText('Matematik').parentElement as HTMLElement
    expect((mathRow.querySelector('select') as HTMLSelectElement).value).toBe('A-')
    const button = screen.getByText('common.continue').closest('button') as HTMLButtonElement
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)
    await waitFor(() => expect(push).toHaveBeenCalledWith('/onboarding/profile'))
    // only the compulsory four are copied — never the rest of the SPM record
    expect(JSON.parse(localStorage.getItem(KEY_SPM_PREREQ) as string)).toEqual({ bm: 'A', eng: 'B+', hist: 'B', math: 'A-' })
  })

  it("never overwrites a grade the block already holds", () => {
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify({ bm: 'C', eng: 'A', hist: 'A', math: 'A' }))
    localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A+' }))
    render(<StpmGradesPage />)
    const bmRow = screen.getByText('Bahasa Melayu').parentElement as HTMLElement
    expect((bmRow.querySelector('select') as HTMLSelectElement).value).toBe('C')
  })
})

// ── STPM CGPA sprint C2 (owner 2026-10-28; mock approved): the CGPA is worked out, the merit apart ──
describe('C2 — the CGPA (PNGK) worked out from the grades, the merit shown separately', () => {
  const ready = (grades: Record<string, string>, koko: string | null = '8') => {
    localStorage.setItem(KEY_STPM_STREAM, 'science')
    localStorage.setItem(KEY_STPM_GRADES, JSON.stringify(grades))
    localStorage.setItem(KEY_MUET_BAND, '4')
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(CORE))
    if (koko !== null) localStorage.setItem(KEY_KOKO_SCORE, koko)
  }
  const continueButton = () => screen.getByText('common.continue').closest('button') as HTMLButtonElement
  const FIVE = { PA: 'A', MATH_T: 'A', PHYSICS: 'A-', CHEMISTRY: 'B+', BIOLOGY: 'C' }

  it('shows the PNGK and the merit as two figures, and marks which subjects count', async () => {
    ready(FIVE)
    render(<StpmGradesPage />)
    await waitFor(() => expect(screen.getByTestId('stpm-cgpa').textContent).toBe('3.75'))
    expect(screen.getByTestId('stpm-merit').textContent).toBe('92.25')
    expect(screen.getByText('onboarding.stpmCgpaLabel')).toBeTruthy()
    expect(screen.getByText('onboarding.meritLabel')).toBeTruthy()
    expect(screen.getByTestId('count-PA').textContent).toBe('onboarding.stpmCountsAlways')
    for (const id of ['MATH_T', 'PHYSICS', 'CHEMISTRY']) {
      expect(screen.getByTestId(`count-${id}`).textContent).toBe('onboarding.stpmCounts')
    }
    expect(screen.getByTestId('count-BIOLOGY').textContent).toBe('onboarding.stpmNotCounted')
    expect(mockCalculateCgpa).toHaveBeenLastCalledWith(FIVE, 8)
  })

  it('below PA + three: no CGPA ("not calculated yet"), the ask to add a subject, and Continue stays off', async () => {
    ready({ PA: 'A', MATH_T: 'A', PHYSICS: 'A-' })
    render(<StpmGradesPage />)
    await waitFor(() => expect(mockCalculateCgpa).toHaveBeenCalled())
    expect(screen.getByTestId('stpm-cgpa').textContent).toBe('—')
    expect(screen.getByText('onboarding.stpmCgpaNotYet')).toBeTruthy()
    expect(screen.getByText('onboarding.stpmCgpaNeedMore')).toBeTruthy()
    expect(screen.queryByTestId('count-PA')).toBeNull()
    expect(continueButton().disabled).toBe(true)
  })

  it('needs a co-curriculum score: no merit without one, and Continue stays off until it is entered', async () => {
    ready(FIVE, null)
    render(<StpmGradesPage />)
    await waitFor(() => expect(screen.getByTestId('stpm-cgpa').textContent).toBe('3.75'))
    expect(screen.getByTestId('stpm-merit').textContent).toBe('—')
    expect(continueButton().disabled).toBe(true)
    for (const bad of ['11', '-1']) {
      fireEvent.change(screen.getByPlaceholderText('0.00 – 10.00'), { target: { value: bad } })
      await waitFor(() => expect(mockCalculateCgpa).toHaveBeenLastCalledWith(FIVE, null))
      expect(continueButton().disabled).toBe(true)
    }
    fireEvent.change(screen.getByPlaceholderText('0.00 – 10.00'), { target: { value: '7.5' } })
    await waitFor(() => expect(continueButton().disabled).toBe(false))
    await waitFor(() => expect(mockCalculateCgpa).toHaveBeenLastCalledWith(FIVE, 7.5))
    await waitFor(() => expect(screen.getByTestId('stpm-merit').textContent).toBe('92.25'))
  })
})
