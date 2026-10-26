/**
 * @jest-environment jsdom
 *
 * "Your Results" — the third results route's page (S2b, the approved mock): which qualification
 * (Matriculation / Asasi (Foundation) / Diploma), for a Diploma where it is from (only a PUBLIC
 * diploma counts, ruling D5), the CGPA as printed, the co-curriculum score (NOT for a Diploma), the
 * MUET band, the live Overall CGPA and Merit from the SERVER's calculator, and the SPM results —
 * required, the STPM page's own block (D4).
 *
 * Rendered, because every claim is about what the page shows or allows after a click.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import HigherGradesPage from './page'
import { calculateHigherCgpa } from '@/lib/api'
import {
  KEY_EXAM_TYPE, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO, KEY_MUET_BAND,
  KEY_RESULTS_EXAM_TYPE, KEY_SPM_PREREQ,
} from '@/lib/storage'

const push = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push, replace: jest.fn() }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/api', () => ({
  calculateHigherCgpa: jest.fn().mockResolvedValue({ cgpa: 3.47, academic_cgpa: 3.5, merit_percent: 86.75 }),
}))
jest.mock('@/components/BrandLogo', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/ProgressStepper', () => ({ __esModule: true, default: () => null }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const calcMock = calculateHigherCgpa as jest.Mock
const SPM_CORE = { bm: 'A', eng: 'A', hist: 'B+', math: 'A' }

const btn = (label: string) => screen.getByText(label).closest('button') as HTMLButtonElement
const continueButton = () => btn('common.continue')
const cgpaInput = () => screen.getByLabelText('onboarding.higherCgpa') as HTMLInputElement
const kokoInput = () => screen.queryByLabelText('onboarding.kokoScore') as HTMLInputElement | null

/** Fill everything except what a test leaves out. */
function fill({ kind = 'matric', cgpa = '3.50', koko = '8', muet = '4', inst = 'public' } = {}) {
  fireEvent.click(btn(`onboarding.higherKind.${kind}`))
  if (kind === 'diploma' && inst) fireEvent.click(btn(`onboarding.higherInst.${inst}`))
  if (cgpa) fireEvent.change(cgpaInput(), { target: { value: cgpa } })
  if (koko && kind !== 'diploma') fireEvent.change(kokoInput() as HTMLInputElement, { target: { value: koko } })
  if (muet) fireEvent.click(btn(muet))
}

beforeEach(() => {
  localStorage.clear()
  push.mockClear()
  calcMock.mockClear()
  jest.useRealTimers()
})

describe('the page per the mock', () => {
  it('asks which qualification first, with the three choices', () => {
    render(<HigherGradesPage />)
    expect(screen.getByText('onboarding.higherGradesTitle')).toBeTruthy()
    expect(screen.getByText('onboarding.higherWhich')).toBeTruthy()
    for (const k of ['matric', 'asasi', 'diploma']) expect(btn(`onboarding.higherKind.${k}`)).toBeTruthy()
    expect(screen.getByText('onboarding.spmPrerequisites')).toBeTruthy()      // the shared SPM block
  })

  it('Diploma HIDES the co-curriculum score and asks where the diploma is from', () => {
    render(<HigherGradesPage />)
    fireEvent.click(btn('onboarding.higherKind.matric'))
    expect(kokoInput()).not.toBeNull()
    expect(screen.queryByText('onboarding.higherWhere')).toBeNull()
    fireEvent.click(btn('onboarding.higherKind.diploma'))
    expect(kokoInput()).toBeNull()
    expect(screen.getByText('onboarding.higherWhere')).toBeTruthy()
    expect(btn('onboarding.higherInst.public')).toBeTruthy()
    expect(btn('onboarding.higherInst.private')).toBeTruthy()
  })

  it('a PRIVATE-college diploma shows the plain message and Continue stays disabled (D5)', () => {
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(SPM_CORE))
    render(<HigherGradesPage />)
    fill({ kind: 'diploma', inst: 'private', cgpa: '3.00' })
    expect(screen.getByText('onboarding.higherPrivateNo')).toBeTruthy()
    expect(continueButton().disabled).toBe(true)
    fireEvent.click(btn('onboarding.higherInst.public'))
    expect(screen.queryByText('onboarding.higherPrivateNo')).toBeNull()
    expect(continueButton().disabled).toBe(false)
  })
})

describe('Continue rules', () => {
  beforeEach(() => localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(SPM_CORE)))

  it('opens only when type, CGPA, koko, MUET and the SPM block are all complete', () => {
    render(<HigherGradesPage />)
    expect(continueButton().disabled).toBe(true)
    fill()
    expect(continueButton().disabled).toBe(false)
  })

  it.each([
    ['no CGPA', { cgpa: '' }],
    ['a CGPA above 4.00', { cgpa: '4.20' }],
    ['a CGPA of 0', { cgpa: '0' }],
    ['no co-curriculum score', { koko: '' }],
    ['a co-curriculum score above 10', { koko: '11' }],
    ['no MUET band', { muet: '' }],
    ['a Diploma with no answer to "where from"', { kind: 'diploma', inst: '' }],
  ])('stays disabled with %s', (_label, missing) => {
    render(<HigherGradesPage />)
    fill(missing)
    expect(continueButton().disabled).toBe(true)
  })

  it('stays disabled until the SPM block is complete (D4)', () => {
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify({ bm: 'A', eng: 'A', hist: 'B+' }))
    render(<HigherGradesPage />)
    fill()
    expect(continueButton().disabled).toBe(true)
    const mathRow = screen.getByText('Matematik').parentElement as HTMLElement
    fireEvent.change(mathRow.querySelector('select') as HTMLSelectElement, { target: { value: 'A-' } })
    expect(continueButton().disabled).toBe(false)
  })

  it('a Diploma needs no co-curriculum score', () => {
    render(<HigherGradesPage />)
    fill({ kind: 'diploma', koko: '' })
    expect(continueButton().disabled).toBe(false)
  })
})

describe('Continue stores the completed form', () => {
  beforeEach(() => localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(SPM_CORE)))

  it('a Matriculation result: the kind as exam AND completion, CGPA, koko, MUET, SPM', async () => {
    render(<HigherGradesPage />)
    fill()
    fireEvent.click(continueButton())
    await waitFor(() => expect(push).toHaveBeenCalledWith('/onboarding/profile'))
    expect(localStorage.getItem(KEY_EXAM_TYPE)).toBe('matric')
    expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('matric')
    expect(localStorage.getItem(KEY_HIGHER_CGPA)).toBe('3.5')
    expect(localStorage.getItem(KEY_HIGHER_KOKO)).toBe('8')
    expect(localStorage.getItem(KEY_MUET_BAND)).toBe('4')
    expect(localStorage.getItem(KEY_HIGHER_INSTITUTION)).toBeNull()
    expect(JSON.parse(localStorage.getItem(KEY_SPM_PREREQ) as string)).toEqual(SPM_CORE)
  })

  it('a Diploma: no co-curriculum score is kept, the institution is', async () => {
    localStorage.setItem(KEY_HIGHER_KOKO, '9')        // left over from an earlier Matriculation entry
    render(<HigherGradesPage />)
    fill({ kind: 'diploma', cgpa: '2.80' })
    fireEvent.click(continueButton())
    await waitFor(() => expect(push).toHaveBeenCalled())
    expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('diploma')
    expect(localStorage.getItem(KEY_HIGHER_KOKO)).toBeNull()
    expect(localStorage.getItem(KEY_HIGHER_INSTITUTION)).toBe('public')
  })

  it('rebuilds from what this browser (or the login hydrate) holds', () => {
    localStorage.setItem(KEY_EXAM_TYPE, 'asasi')
    localStorage.setItem(KEY_HIGHER_CGPA, '3.2')
    localStorage.setItem(KEY_HIGHER_KOKO, '7')
    localStorage.setItem(KEY_MUET_BAND, '3')
    render(<HigherGradesPage />)
    expect(cgpaInput().value).toBe('3.2')
    expect((kokoInput() as HTMLInputElement).value).toBe('7')
    expect(continueButton().disabled).toBe(false)
  })
})

describe('the live figures come from the SERVER calculator, never a copy of the formula', () => {
  it('asks the calculator with the kind, CGPA and koko, and shows its overall CGPA and merit', async () => {
    jest.useFakeTimers()
    render(<HigherGradesPage />)
    fill({ muet: '' })
    await act(async () => { jest.advanceTimersByTime(500) })
    jest.useRealTimers()
    await waitFor(() => expect(screen.getByText('3.47')).toBeTruthy())
    expect(calcMock).toHaveBeenLastCalledWith('matric', 3.5, 8)
    expect(screen.getByText('86.75')).toBeTruthy()
    expect(screen.getByText('onboarding.cgpaLabel')).toBeTruthy()
    expect(screen.getByText('onboarding.meritLabel')).toBeTruthy()
  })

  it('a Diploma is sent with no co-curriculum score', async () => {
    jest.useFakeTimers()
    render(<HigherGradesPage />)
    fill({ kind: 'diploma', cgpa: '2.80', muet: '' })
    await act(async () => { jest.advanceTimersByTime(500) })
    jest.useRealTimers()
    await waitFor(() => expect(calcMock).toHaveBeenCalled())
    expect(calcMock).toHaveBeenLastCalledWith('diploma', 2.8, null)
  })

  it('an incomplete entry asks nothing and shows no figure', async () => {
    jest.useFakeTimers()
    render(<HigherGradesPage />)
    fireEvent.click(btn('onboarding.higherKind.asasi'))
    fireEvent.change(cgpaInput(), { target: { value: '3.1' } })          // no koko yet
    await act(async () => { jest.advanceTimersByTime(500) })
    jest.useRealTimers()
    expect(calcMock).not.toHaveBeenCalled()
    expect(screen.queryByText('onboarding.meritLabel')).toBeNull()
  })
})
