/**
 * @jest-environment jsdom
 *
 * "Choose Your Exam" — the third card (third results route S2b, approved mock): "Matriculation,
 * Asasi or Diploma", subtitle "STPM-equivalent qualifications", in the same card style as SPM and
 * STPM. A tap only SELECTS (it opens the results page); nothing is recorded as completed here.
 */
import { fireEvent, render, screen } from '@testing-library/react'

import ExamTypePage from './page'
import { KEY_EXAM_TYPE, KEY_RESULTS_EXAM_TYPE } from '@/lib/storage'

const push = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/components/BrandLogo', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/ProgressStepper', () => ({ __esModule: true, default: () => null }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

beforeEach(() => { localStorage.clear(); push.mockClear() })

const card = (title: string) => screen.getByText(title).closest('button') as HTMLButtonElement

it('shows three cards, the third titled and subtitled per the mock, styled like the others', () => {
  render(<ExamTypePage />)
  const third = card('onboarding.higherCardTitle')
  expect(third).toBeTruthy()
  expect(third.textContent).toContain('onboarding.higherCardDesc')
  expect(third.className).toBe(card('STPM').className)
  expect(screen.getAllByRole('button')).toHaveLength(3)
})

it('the third card opens the new results page and records nothing as completed', () => {
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
  render(<ExamTypePage />)
  fireEvent.click(card('onboarding.higherCardTitle'))
  expect(push).toHaveBeenCalledWith('/onboarding/higher-grades')
  expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('spm')
})

it('SPM and STPM still go where they went', () => {
  render(<ExamTypePage />)
  fireEvent.click(card('SPM'))
  expect(push).toHaveBeenLastCalledWith('/onboarding/grades')
  expect(localStorage.getItem(KEY_EXAM_TYPE)).toBe('spm')
  fireEvent.click(card('STPM'))
  expect(push).toHaveBeenLastCalledWith('/onboarding/stpm-grades')
  expect(localStorage.getItem(KEY_EXAM_TYPE)).toBe('stpm')
})
