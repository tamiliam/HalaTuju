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
  KEY_EXAM_TYPE, KEY_GRADES, KEY_HIGHER_CGPA, KEY_KOKO_SCORE, KEY_RESULTS_COMPLETED_AT,
  KEY_RESULTS_EXAM_TYPE, KEY_SPM_PREREQ, KEY_STPM_CGPA, KEY_STPM_GRADES,
} from '@/lib/storage'
import { resultsSyncFields, signInResultsFields } from '@/lib/resultsSync'

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

// Pre-U sprint, review rounds 1 and 2: after the switch to SPM (maybe on another device) the server
// holds SPM only and carries the switch's stamp. A browser copy not completed after the stamp is
// dropped BEFORE the pending-move-up check, so no later sync sends it back up.
const STAMP = '2026-11-26T08:00:00Z'
const SERVER_SWITCHED = {
  ...SERVER_SPM, stpm_grades: {}, completed_qualifications: ['spm'], held_results_cleared_at: STAMP,
}

it.each([
  ['no completion time', null],
  ['a completion time before the switch', '2026-11-25T08:00:00.000Z'],
])('a stale local STPM completion (%s) is dropped although it reads as a move up', async (_l, at) => {
  localStorage.setItem(KEY_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
  if (at) localStorage.setItem(KEY_RESULTS_COMPLETED_AT, at)
  localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A' }))
  localStorage.setItem(KEY_STPM_CGPA, '3.42')
  localStorage.setItem(KEY_KOKO_SCORE, '8')
  localStorage.setItem(KEY_HIGHER_CGPA, '3.1')
  mockProfile = SERVER_SWITCHED
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_STPM_GRADES)).toBeNull())
  expect([KEY_STPM_CGPA, KEY_KOKO_SCORE, KEY_HIGHER_CGPA, KEY_RESULTS_COMPLETED_AT]
    .map((k) => localStorage.getItem(k))).toEqual([null, null, null, null])
  expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('spm')         // the server's, so no move up
  expect(localStorage.getItem(KEY_EXAM_TYPE)).toBe('spm')
  expect(resultsSyncFields(localStorage).results_exam_type).toBe('spm')  // the next sync sends SPM
  expect(localStorage.getItem(KEY_GRADES)).not.toBeNull()                 // the SPM results stay
})

it('an STPM entry completed after the switch is kept and sent with its time', async () => {
  localStorage.setItem(KEY_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_RESULTS_COMPLETED_AT, '2026-11-26T09:00:00.000Z')
  localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A' }))
  mockProfile = SERVER_SWITCHED
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_GRADES)).not.toBeNull())
  expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('stpm')
  expect(JSON.parse(localStorage.getItem(KEY_STPM_GRADES) as string)).toEqual({ PA: 'A' })
  expect(signInResultsFields(localStorage, SERVER_SWITCHED)).toMatchObject({
    results_exam_type: 'stpm', results_completed_at: '2026-11-26T09:00:00.000Z',
  })
})

it('a student who never switched (no stamp) keeps the local copies as before', async () => {
  localStorage.setItem(KEY_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A' }))
  mockProfile = { ...SERVER_SWITCHED, held_results_cleared_at: null }
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_GRADES)).not.toBeNull())
  expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('stpm')
  expect(JSON.parse(localStorage.getItem(KEY_STPM_GRADES) as string)).toEqual({ PA: 'A' })
})

it('a server that still holds STPM results keeps the local copies', async () => {
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
  localStorage.setItem(KEY_STPM_CGPA, '3.42')
  mockProfile = { ...SERVER_SWITCHED, stpm_grades: { PA: 'C' } }           // stpm_grades on file
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_GRADES)).not.toBeNull())
  expect(localStorage.getItem(KEY_STPM_CGPA)).toBe('3.42')
})

it('an unparseable cleared-at stamp skips the drop, so no local data is lost', async () => {
  localStorage.setItem(KEY_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
  localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A' }))
  mockProfile = { ...SERVER_SWITCHED, held_results_cleared_at: 'not-a-date' }
  render(<AuthProvider><div>app</div></AuthProvider>)
  await waitFor(() => expect(localStorage.getItem(KEY_GRADES)).not.toBeNull())
  expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('stpm')
  expect(JSON.parse(localStorage.getItem(KEY_STPM_GRADES) as string)).toEqual({ PA: 'A' })
})
