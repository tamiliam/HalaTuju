/**
 * @jest-environment jsdom
 *
 * The SPM grades page, rendered.
 *
 * ⚠ THIS IS THE FIRST RENDERED TEST ON A STUDENT ONBOARDING PAGE, and it exists because the bug it
 * pins was invisible to every other kind of check. The page used to start on the SCIENCE stream and
 * PRE-FILL its four stream slots, then save whichever slots still named a subject — graded or not.
 * An arts student who never touched Section 3 therefore SAVED Physics, Chemistry, Biology and Add
 * Maths as the subjects she sat. Nothing failed; the merit engine simply scored a subject she never
 * took at G inside the 30% stream band. Measured on production 2026-09-02: 15 profiles, 9 of them
 * bursary applicants, losing 7-15 merit points each.
 *
 * All three claims below are about MOUNT-TIME and POST-CLICK STATE, which a source-shape guard
 * cannot see: it would happily pass while the pre-fill ran in an effect.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import GradesInputPage from './page'
import { SPM_CORE_SUBJECTS } from '@/lib/subjects'
import { KEY_ALIRAN, KEY_ELEKTIF, KEY_GRADES, KEY_STREAM } from '@/lib/storage'

const push = jest.fn()

jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/api', () => ({
  calculateMerit: jest.fn().mockResolvedValue({ academic_merit: 80, final_merit: 85 }),
}))
jest.mock('@/components/BrandLogo', () => ({
  __esModule: true, default: () => null,
}))
jest.mock('@/components/ProgressStepper', () => ({
  __esModule: true, default: () => null,
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

/** Every core subject at A — the only thing that unlocks Continue. */
const allCoresGraded = () =>
  Object.fromEntries(SPM_CORE_SUBJECTS.map((s) => [s.id, 'A']))

/**
 * The current value of every subject dropdown on the page, in render order.
 *
 * ⚠ Counting the "select a subject" placeholder is NOT enough — every subject dropdown renders
 * that option whether or not a subject is chosen, so a count of four says nothing about whether
 * the page filled them in. The VALUES are the claim. (Stream rows first, then elective rows;
 * these tests seed no electives except where noted.)
 */
const subjectSelectValues = () =>
  screen
    .queryAllByText('onboarding.selectSubject')
    .map((option) => (option.closest('select') as HTMLSelectElement).value)

beforeEach(() => {
  localStorage.clear()
  push.mockClear()
})

describe('the stream slots are never filled in on the student behalf', () => {
  it('offers no stream subject at all until a stream is chosen', () => {
    render(<GradesInputPage />)

    // The section says what to do instead of showing four dropdowns with nothing in them.
    expect(screen.getByText('onboarding.pickStreamFirst')).toBeTruthy()
    expect(subjectSelectValues()).toEqual([])
  })

  it('leaves all four slots EMPTY after a stream is chosen', () => {
    render(<GradesInputPage />)

    fireEvent.click(screen.getByText('onboarding.scienceStream'))

    // Four rows appear and every one is blank. Before the fix these came back pre-set to
    // Physics / Chemistry / Biology / Add Maths, and a student who scrolled past kept them.
    expect(screen.queryByText('onboarding.pickStreamFirst')).toBeNull()
    expect(subjectSelectValues()).toEqual(['', '', '', ''])
  })

  it('empties the slots again when the student changes stream', () => {
    localStorage.setItem(KEY_STREAM, 'science')
    localStorage.setItem(KEY_ALIRAN, JSON.stringify(['phy', 'chem']))
    localStorage.setItem(KEY_GRADES, JSON.stringify({ ...allCoresGraded(), phy: 'A', chem: 'B' }))
    render(<GradesInputPage />)

    // Two slots come back from the saved record; the other two stay blank.
    expect(subjectSelectValues()).toEqual(['phy', 'chem', '', ''])

    fireEvent.click(screen.getByText('onboarding.artsStream'))

    // Changing stream must not re-guess from the ARTS pool either — all four go blank.
    expect(subjectSelectValues()).toEqual(['', '', '', ''])
  })
})

describe('saving records only subjects that carry a grade', () => {
  it('drops a named-but-ungraded stream subject', async () => {
    localStorage.setItem(KEY_STREAM, 'science')
    localStorage.setItem(KEY_ALIRAN, JSON.stringify(['phy', 'chem']))
    localStorage.setItem(KEY_ELEKTIF, JSON.stringify(['b_tamil']))
    // Physics is graded; Chemistry and Bahasa Tamil are named with nothing behind them.
    localStorage.setItem(KEY_GRADES, JSON.stringify({ ...allCoresGraded(), phy: 'A' }))
    render(<GradesInputPage />)

    fireEvent.click(screen.getByText('common.continue'))

    await waitFor(() => expect(push).toHaveBeenCalledWith('/onboarding/profile'))
    expect(JSON.parse(localStorage.getItem(KEY_ALIRAN) as string)).toEqual(['phy'])
    expect(JSON.parse(localStorage.getItem(KEY_ELEKTIF) as string)).toEqual([])
  })

  it('keeps every stream subject the student actually graded', async () => {
    localStorage.setItem(KEY_STREAM, 'science')
    localStorage.setItem(KEY_ALIRAN, JSON.stringify(['phy', 'chem']))
    localStorage.setItem(
      KEY_GRADES,
      JSON.stringify({ ...allCoresGraded(), phy: 'A', chem: 'B+' }),
    )
    render(<GradesInputPage />)

    fireEvent.click(screen.getByText('common.continue'))

    await waitFor(() => expect(push).toHaveBeenCalledWith('/onboarding/profile'))
    expect(JSON.parse(localStorage.getItem(KEY_ALIRAN) as string)).toEqual(['phy', 'chem'])
  })
})
