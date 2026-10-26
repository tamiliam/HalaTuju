/**
 * @jest-environment jsdom
 *
 * Third results route S2b — finishing onboarding SENDS the results as one set: the exam, the
 * recorded completion, the WHOLE `completed_qualifications` list (the server REPLACES it on every
 * sync and ranks "highest" over it) and, for Matriculation / Asasi / Diploma, the CGPA, the
 * co-curriculum score (none for Diploma) and where a Diploma is from. Rendered, because the claim
 * is about what one click on the real page puts on the wire.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProfileInputPage from './page'
import { getProfile, syncProfile } from '@/lib/api'
import {
  KEY_EXAM_TYPE, KEY_GRADES, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO, KEY_PROFILE,
  KEY_RESULTS_EXAM_TYPE, KEY_SPM_PREREQ, KEY_STPM_CGPA, KEY_STPM_GRADES,
} from '@/lib/storage'

const push = jest.fn()

jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ token: 'tkn', isAnonymous: false, refreshProfile: jest.fn(() => Promise.resolve()) }),
}))
jest.mock('@/lib/api', () => ({
  getProfile: jest.fn(),
  syncProfile: jest.fn(() => Promise.resolve({})),
}))
jest.mock('@/components/BrandLogo', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/ProgressStepper', () => ({ __esModule: true, default: () => null }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const syncMock = syncProfile as jest.Mock
const SPM = { bm: 'A', eng: 'A', hist: 'B+', math: 'A' }

async function finish() {
  render(<ProfileInputPage />)
  await waitFor(() => expect(getProfile).toHaveBeenCalled())
  await act(async () => { await Promise.resolve() })
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /onboarding\.seeRecommendations/ }))
  })
  await waitFor(() => expect(syncMock).toHaveBeenCalled())
  return syncMock.mock.calls[0][0]
}

beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
  ;(getProfile as jest.Mock).mockResolvedValue({ gender: 'female' })
  localStorage.setItem(KEY_PROFILE, JSON.stringify({ gender: 'female' }))
})

it('an Asasi completion: CGPA, koko, MUET-free set and the full list [spm, asasi]', async () => {
  localStorage.setItem(KEY_EXAM_TYPE, 'asasi')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'asasi')
  localStorage.setItem(KEY_HIGHER_CGPA, '3.2')
  localStorage.setItem(KEY_HIGHER_KOKO, '7')
  localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(SPM))
  const sent = await finish()
  expect(sent).toMatchObject({
    exam_type: 'asasi', results_exam_type: 'asasi', higher_cgpa: 3.2, higher_koko: 7,
    higher_institution_type: '', completed_qualifications: ['spm', 'asasi'], spm_prereq_grades: SPM,
  })
})

it('a public Diploma: no co-curriculum score, the institution type sent', async () => {
  localStorage.setItem(KEY_EXAM_TYPE, 'diploma')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'diploma')
  localStorage.setItem(KEY_HIGHER_CGPA, '2.8')
  localStorage.setItem(KEY_HIGHER_INSTITUTION, 'public')
  localStorage.setItem(KEY_HIGHER_KOKO, '9')          // left over from an earlier Matriculation entry
  const sent = await finish()
  expect(sent).toMatchObject({
    higher_cgpa: 2.8, higher_koko: null, higher_institution_type: 'public',
    completed_qualifications: ['spm', 'diploma'],
  })
})

it('SPM and STPM completions send their whole list too, and nothing of the third route', async () => {
  localStorage.setItem(KEY_EXAM_TYPE, 'spm')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
  localStorage.setItem(KEY_GRADES, JSON.stringify(SPM))
  let sent = await finish()
  expect(sent.completed_qualifications).toEqual(['spm'])
  expect(sent).not.toHaveProperty('higher_cgpa')

  jest.clearAllMocks()
  document.body.innerHTML = ''
  localStorage.setItem(KEY_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A', MATH_T: 'A', PHYSICS: 'B', CHEMISTRY: 'B' }))
  localStorage.setItem(KEY_STPM_CGPA, '3.5')
  sent = await finish()
  expect(sent.results_exam_type).toBe('stpm')
  expect(sent.completed_qualifications).toEqual(['spm', 'stpm'])
  expect(sent).not.toHaveProperty('higher_cgpa')
})

it('release safety: a 400 third_route_closed is retried ONCE without the third-route results', async () => {
  const closed = Object.assign(new Error('API error: 400'), {
    status: 400, fieldErrors: { error: ['third_route_closed'], higher_cgpa: ['not open'] },
  })
  syncMock.mockRejectedValueOnce(closed)
  const warn = jest.spyOn(console, 'warn').mockImplementation(() => {})
  localStorage.setItem(KEY_EXAM_TYPE, 'matric')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'matric')
  localStorage.setItem(KEY_HIGHER_CGPA, '3.5')
  localStorage.setItem(KEY_HIGHER_KOKO, '8')
  localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(SPM))
  await finish()
  await waitFor(() => expect(syncMock).toHaveBeenCalledTimes(2))
  const retry = syncMock.mock.calls[1][0]
  for (const k of ['exam_type', 'results_exam_type', 'completed_qualifications', 'higher_cgpa', 'higher_koko']) {
    expect(retry).not.toHaveProperty(k)
  }
  expect(retry.spm_prereq_grades).toEqual(SPM)            // the rest of the sync is not lost
  expect(retry.gender).toBe('female')
  expect(warn).toHaveBeenCalled()
  warn.mockRestore()
})

it('any other failure is not retried', async () => {
  syncMock.mockRejectedValueOnce(Object.assign(new Error('API error: 500'), { status: 500 }))
  localStorage.setItem(KEY_EXAM_TYPE, 'spm')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
  await finish()
  await act(async () => { await Promise.resolve() })
  expect(syncMock).toHaveBeenCalledTimes(1)
})
