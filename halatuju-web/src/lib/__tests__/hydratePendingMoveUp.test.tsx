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
  KEY_EXAM_TYPE, KEY_GRADES, KEY_HIGHER_CGPA, KEY_KOKO_SCORE, KEY_RESULTS_EXAM_TYPE, KEY_SPM_PREREQ,
  KEY_STPM_CGPA, KEY_STPM_GRADES,
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

// Pre-U sprint, review round 1 (finding 3): after the switch to SPM (maybe on another device) the
// server holds SPM only — this browser's old STPM / third-route copies are dropped, so no later sync
// sends them back up.
it('an SPM-only server profile drops the stale local STPM and third-route copies', async () => {
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
  localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A' }))
  localStorage.setItem(KEY_STPM_CGPA, '3.42')
  localStorage.setItem(KEY_KOKO_SCORE, '8')
  localStorage.setItem(KEY_HIGHER_CGPA, '3.1')
  mockProfile = { ...SERVER_SPM, stpm_grades: {}, completed_qualifications: ['spm'] }
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_STPM_GRADES)).toBeNull())
  expect(localStorage.getItem(KEY_STPM_CGPA)).toBeNull()
  expect(localStorage.getItem(KEY_KOKO_SCORE)).toBeNull()
  expect(localStorage.getItem(KEY_HIGHER_CGPA)).toBeNull()
  expect(localStorage.getItem(KEY_GRADES)).not.toBeNull()                 // the SPM results stay
})

it('a server that still holds STPM results keeps the local copies', async () => {
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
  localStorage.setItem(KEY_STPM_CGPA, '3.42')
  mockProfile = { ...SERVER_SPM, completed_qualifications: ['spm'] }     // stpm_grades on file
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_GRADES)).not.toBeNull())
  expect(localStorage.getItem(KEY_STPM_CGPA)).toBe('3.42')
})
