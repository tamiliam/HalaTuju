/**
 * @jest-environment jsdom
 *
 * S2b round 2 (finding B) — the login hydrate must not overwrite a NEWER tertiary completion this
 * browser holds (entered while signed out) with the server's older SPM answer before the sign-in
 * sync can send it. Mounts the REAL AuthProvider, so the hydrate is the one every route runs.
 */
import { render, waitFor } from '@testing-library/react'

import { AuthProvider } from '@/lib/auth-context'
import {
  KEY_EXAM_TYPE, KEY_GRADES, KEY_HIGHER_CGPA, KEY_RESULTS_EXAM_TYPE, KEY_SPM_PREREQ, KEY_STPM_GRADES,
} from '@/lib/storage'

let mockProfile: Record<string, unknown> = {}
jest.mock('next/navigation', () => ({ usePathname: () => '/dashboard' }))
jest.mock('@/lib/api', () => ({ getProfile: jest.fn(() => Promise.resolve(mockProfile)) }))
jest.mock('@/lib/supabase', () => ({
  getSession: () => Promise.resolve({ session: { access_token: 'tkn', user: { is_anonymous: false } } }),
  signInAnonymously: jest.fn(),
  getSupabase: () => ({
    auth: { onAuthStateChange: () => ({ data: { subscription: { unsubscribe: jest.fn() } } }) },
  }),
}))

const SERVER_SPM = {
  nric: '900101-01-1234', exam_type: 'spm', results_exam_type: 'spm', results_held: 'spm',
  grades: { bm: 'A' }, spm_prereq_grades: { bm: 'C' }, stpm_grades: { PA: 'C' },
}

beforeEach(() => localStorage.clear())

it.each([
  ['Matriculation', 'matric', { [KEY_HIGHER_CGPA]: '3.5' }],
  ['STPM', 'stpm', { [KEY_STPM_GRADES]: JSON.stringify({ PA: 'A' }) }],
])('a %s completion entered signed out survives the hydrate', async (_l, kind, extra) => {
  localStorage.setItem(KEY_EXAM_TYPE, kind)
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, kind)
  localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify({ bm: 'A+' }))
  for (const [k, v] of Object.entries(extra)) localStorage.setItem(k, v)
  mockProfile = SERVER_SPM
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_GRADES)).not.toBeNull())   // the hydrate ran
  expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe(kind)
  expect(localStorage.getItem(KEY_EXAM_TYPE)).toBe(kind)
  expect(JSON.parse(localStorage.getItem(KEY_SPM_PREREQ) as string)).toEqual({ bm: 'A+' })
  if (kind === 'stpm') expect(JSON.parse(localStorage.getItem(KEY_STPM_GRADES) as string)).toEqual({ PA: 'A' })
})

it('with no pending move up the hydrate writes the server answer as before', async () => {
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
  mockProfile = { ...SERVER_SPM, results_exam_type: 'stpm', results_held: 'stpm', exam_type: 'stpm' }
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('stpm'))
  expect(JSON.parse(localStorage.getItem(KEY_SPM_PREREQ) as string)).toEqual({ bm: 'C' })
})
