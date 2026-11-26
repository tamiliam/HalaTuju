/**
 * @jest-environment jsdom
 *
 * Pre-U sprint: "Switch to SPM results?" on /onboarding/exam-type. A student the server says holds
 * STPM results is asked before the SPM form opens; yes only RECORDS the choice (nothing is removed
 * until the SPM grades are saved); Back forgets it. A locked student is offered Back only.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import ExamTypePage from './page'
import { KEY_CLEAR_HELD_PENDING, KEY_EXAM_TYPE } from '@/lib/storage'

const push = jest.fn()
let profile: Record<string, unknown> | null = null
jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({ profile }) }))
jest.mock('@/components/FlowHeader', () => ({ __esModule: true, default: () => null }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))
jest.mock('@/lib/i18n', () => ({
  ...jest.requireActual('@/lib/i18n'),
  useT: () => ({
    t: (k: string, p?: Record<string, string>) => (k === 'onboarding.switchSpmHeld'
      ? `You entered <b>${p?.route}</b> results before: <b>${p?.summary}</b>` : p ? `${k}|${p.route ?? ''}` : k),
    locale: 'en',
  }),
}))

beforeEach(() => { localStorage.clear(); push.mockClear(); profile = null })
const tapSpm = () => fireEvent.click(screen.getByText('SPM').closest('button') as HTMLButtonElement)

describe('exam-type: the switch to SPM', () => {
  it('an SPM-only (or signed-out) student goes straight to the SPM form', () => {
    profile = { results_held: 'spm' }
    render(<ExamTypePage />)
    tapSpm()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(push).toHaveBeenCalledWith('/onboarding/grades')
    expect(localStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBeNull()
  })

  it('an STPM student is asked first, with her held results', () => {
    profile = { results_held: 'stpm', stpm_cgpa: 3.42 }
    render(<ExamTypePage />)
    tapSpm()
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByText('onboarding.switchSpmTitle')).toBeTruthy()
    expect(screen.getByText('STPM PNGK 3.42').tagName).toBe('B')
    expect(screen.getByText('onboarding.switchSpmNothing')).toBeTruthy()
    expect(push).not.toHaveBeenCalled()
  })

  it('yes records the choice and opens the SPM form (nothing is cleared yet)', () => {
    profile = { results_held: 'stpm', stpm_cgpa: 3.42 }
    render(<ExamTypePage />)
    tapSpm()
    fireEvent.click(screen.getByText('onboarding.switchSpmConfirm'))
    expect(localStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBe('confirmed')
    expect(localStorage.getItem(KEY_EXAM_TYPE)).toBe('spm')
    expect(push).toHaveBeenCalledWith('/onboarding/grades')
  })

  it('Back closes the dialog and changes nothing', () => {
    profile = { results_held: 'stpm', stpm_cgpa: 3.42 }
    render(<ExamTypePage />)
    tapSpm()
    fireEvent.click(screen.getByText('common.back', { selector: '[role="dialog"] button' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(localStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBeNull()
    expect(localStorage.getItem(KEY_EXAM_TYPE)).toBeNull()
    expect(push).not.toHaveBeenCalled()
  })

  it('a locked student is told why and offered Back only', () => {
    profile = { results_held: 'stpm', stpm_cgpa: 3.42, held_results_locked: true }
    render(<ExamTypePage />)
    tapSpm()
    expect(screen.getByText(/onboarding\.switchSpmLocked/)).toBeTruthy()
    expect(screen.queryByText('onboarding.switchSpmConfirm')).toBeNull()
  })

  it('choosing STPM instead forgets a pending switch', () => {
    localStorage.setItem(KEY_CLEAR_HELD_PENDING, 'confirmed')
    render(<ExamTypePage />)
    fireEvent.click(screen.getByText('STPM').closest('button') as HTMLButtonElement)
    expect(localStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBeNull()
  })
})
