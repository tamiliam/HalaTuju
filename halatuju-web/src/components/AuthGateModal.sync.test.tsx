/**
 * @jest-environment jsdom
 *
 * TD-069 review F2 — the sign-in gate SENDS what the login hydrate is about to overwrite.
 *
 * The race: a student enters SPM prerequisites on device B, signed out, then signs in. The
 * provider's hydrate writes the server's copies (device A's, older) into localStorage on every
 * sign-in. The gate's sync reads localStorage FIRST — so whatever it sends reaches the server, and
 * whatever it leaves out is silently replaced by device A's copy. Before the fix it left out the
 * STPM path's three fields (and v2.21.0's `elective_subjects`).
 *
 * `t` echoes its key.
 */
import { render, waitFor } from '@testing-library/react'

import AuthGateModal from './AuthGateModal'
import * as api from '@/lib/api'
import {
  KEY_ELEKTIF, KEY_EXAM_TYPE, KEY_GRADES, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO,
  KEY_PROFILE, KEY_RESULTS_EXAM_TYPE, KEY_SPM_ELEKTIF, KEY_SPM_PREREQ, KEY_SPM_STREAM, KEY_STPM_GRADES,
} from '@/lib/storage'

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/dashboard',
}))
jest.mock('@/lib/supabase', () => ({
  signInWithPhone: jest.fn(), verifyOTP: jest.fn(), signInWithGoogle: jest.fn(),
}))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  claimNric: jest.fn(),
  syncProfile: jest.fn(() => Promise.resolve({})),
  // The server's profile at sign-in: by default it records no completion yet (a first onboarding).
  getProfile: jest.fn(() => Promise.resolve({ results_exam_type: '', completed_qualifications: [] })),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({
    authGateReason: 'save',
    authGateCourseId: null,
    hideAuthGate: jest.fn(),
    isAuthenticated: true,          // a RETURNING user: the gate syncs and closes
    isAnonymous: false,
    token: 'tkn',
    session: { user: { user_metadata: {} } },
    status: 'ready',
    profile: null,
    refreshProfile: jest.fn(() => Promise.resolve()),
  }),
}))

const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => {
  localStorage.clear()
  jest.clearAllMocks()
})

it("sends this device's STPM-path SPM prerequisites before the hydrate can replace them", async () => {
  const fresh = { bm: 'A+', eng: 'A', hist: 'A', math: 'A', ekonomi: 'A', geo: 'B+' }
  localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(fresh))
  localStorage.setItem(KEY_SPM_ELEKTIF, JSON.stringify(['ekonomi', 'geo']))
  localStorage.setItem(KEY_SPM_STREAM, 'arts')
  localStorage.setItem(KEY_ELEKTIF, JSON.stringify(['poa']))
  localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A' }))

  render(<AuthGateModal />)

  await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
  const sent = mockApi.syncProfile.mock.calls[0][0]
  expect(sent.spm_prereq_grades).toEqual(fresh)
  expect(sent.spm_elective_subjects).toEqual(['ekonomi', 'geo'])
  expect(sent.spm_stream).toBe('arts')
  expect(sent.elective_subjects).toEqual(['poa'])
  // positive control: the fields the gate always sent are still sent
  expect(sent.grades).toEqual({ bm: 'A' })
})

it('sends none of them when this device never entered any', async () => {
  localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A' }))
  render(<AuthGateModal />)
  await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
  const sent = mockApi.syncProfile.mock.calls[0][0]
  expect(sent).not.toHaveProperty('spm_prereq_grades')
  expect(sent).not.toHaveProperty('spm_elective_subjects')
  expect(sent).not.toHaveProperty('spm_stream')
  expect(sent.grades).toEqual({ bm: 'A' })
})

// ── Third results route S2b: the results travel as a SET, the completed list whole ──────────
describe('the results half of the sign-in sync (third results route S2b)', () => {
  it('sends a Matriculation completion with its CGPA, koko and the FULL completed list', async () => {
    localStorage.setItem(KEY_EXAM_TYPE, 'matric')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'matric')
    localStorage.setItem(KEY_HIGHER_CGPA, '3.5')
    localStorage.setItem(KEY_HIGHER_KOKO, '8')
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify({ bm: 'A', eng: 'A', hist: 'B', math: 'A' }))
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    const sent = mockApi.syncProfile.mock.calls[0][0]
    expect(sent).toMatchObject({
      exam_type: 'matric', results_exam_type: 'matric', higher_cgpa: 3.5, higher_koko: 8,
      higher_institution_type: '', completed_qualifications: ['spm', 'matric'],
    })
    expect(sent.spm_prereq_grades).toEqual({ bm: 'A', eng: 'A', hist: 'B', math: 'A' })
  })

  it('a Diploma sends no co-curriculum score and says where it is from', async () => {
    localStorage.setItem(KEY_EXAM_TYPE, 'diploma')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'diploma')
    localStorage.setItem(KEY_HIGHER_CGPA, '2.8')
    localStorage.setItem(KEY_HIGHER_KOKO, '9')          // left over from a Matriculation entry
    localStorage.setItem(KEY_HIGHER_INSTITUTION, 'public')
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    expect(mockApi.syncProfile.mock.calls[0][0]).toMatchObject({
      higher_cgpa: 2.8, higher_koko: null, higher_institution_type: 'public',
      completed_qualifications: ['spm', 'diploma'],
    })
  })

  it('an STPM completion sends its list and never touches the third-route fields', async () => {
    localStorage.setItem(KEY_EXAM_TYPE, 'stpm')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
    localStorage.setItem(KEY_HIGHER_CGPA, '3.1')         // an abandoned third-route entry
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    const sent = mockApi.syncProfile.mock.calls[0][0]
    expect(sent.results_exam_type).toBe('stpm')
    expect(sent.completed_qualifications).toEqual(['spm', 'stpm'])
    expect(sent).not.toHaveProperty('higher_cgpa')
  })

  it('a browser that never completed a results form sends neither the marker nor a list', async () => {
    localStorage.setItem(KEY_EXAM_TYPE, 'asasi')        // a card tap, nothing completed
    localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A' }))
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    const sent = mockApi.syncProfile.mock.calls[0][0]
    expect(sent.exam_type).toBe('asasi')
    expect(sent).not.toHaveProperty('results_exam_type')
    expect(sent).not.toHaveProperty('completed_qualifications')
  })
})

// ── S2b adversarial review (HIGH): the sign-in door never overwrites a RECORDED completion ──────
describe('a stale browser at sign-in leaves a recorded completion alone', () => {
  const staleSpm = () => {
    localStorage.setItem(KEY_EXAM_TYPE, 'spm')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A' }))
  }
  it.each([
    ['a legacy STPM holder (recorded stpm, blank list)', { results_exam_type: 'stpm', completed_qualifications: [] }],
    ["an ['spm','stpm'] holder", { results_exam_type: 'stpm', completed_qualifications: ['spm', 'stpm'] }],
    ['a Matriculation holder', { results_exam_type: 'matric', completed_qualifications: ['spm', 'matric'] }],
    ['a list with no marker', { results_exam_type: '', completed_qualifications: ['spm', 'stpm'] }],
  ])('%s: no marker, no list, no exam type is sent', async (_label, server) => {
    mockApi.getProfile.mockResolvedValueOnce(server as never)
    staleSpm()
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    const sent = mockApi.syncProfile.mock.calls[0][0]
    expect(sent).not.toHaveProperty('results_exam_type')
    expect(sent).not.toHaveProperty('completed_qualifications')
    expect(sent).not.toHaveProperty('exam_type')
    expect(sent.grades).toEqual({ bm: 'A' })              // the rest of the sync still goes
  })

  // Round 1 also pinned "a recorded SPM account is not PROMOTED by an STPM browser". Round 2
  // (finding B) SUPERSEDED that: a move UP from held SPM is sent, or a returning SPM student's new
  // results are lost — see the describe below. What stays pinned: no move, nothing sent.
  it('a recorded SPM account whose browser also says SPM: nothing is sent', async () => {
    mockApi.getProfile.mockResolvedValueOnce(
      { results_exam_type: 'spm', completed_qualifications: ['spm'], results_held: 'spm' } as never)
    localStorage.setItem(KEY_EXAM_TYPE, 'spm')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    expect(mockApi.syncProfile.mock.calls[0][0]).not.toHaveProperty('results_exam_type')
  })

  it('an unreadable server profile sends no results set (cautious)', async () => {
    mockApi.getProfile.mockRejectedValueOnce(new Error('down'))
    staleSpm()
    localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A' }))
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    const sent = mockApi.syncProfile.mock.calls[0][0]
    expect(sent).not.toHaveProperty('results_exam_type')
    expect(sent.stpm_grades).toEqual({ PA: 'A' })        // and nothing after it was skipped
  })

  it('an empty browser sends nothing of the results set', async () => {
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    const sent = mockApi.syncProfile.mock.calls[0][0]
    for (const k of ['exam_type', 'results_exam_type', 'completed_qualifications', 'higher_cgpa']) {
      expect(sent).not.toHaveProperty(k)
    }
  })
})

// ── S2b round 2 (finding B): a RETURNING SPM account that entered new tertiary results signed out ──
describe('a move UP is sent at sign-in; the server still refuses a move down', () => {
  const SERVER_SPM = { results_exam_type: 'spm', completed_qualifications: ['spm'], results_held: 'spm' }

  it('STPM results entered while signed out reach an account recorded SPM', async () => {
    mockApi.getProfile.mockResolvedValueOnce(SERVER_SPM as never)
    localStorage.setItem(KEY_EXAM_TYPE, 'stpm')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
    localStorage.setItem(KEY_STPM_GRADES, JSON.stringify({ PA: 'A', MATH_T: 'A' }))
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    const sent = mockApi.syncProfile.mock.calls[0][0]
    expect(sent).toMatchObject({ exam_type: 'stpm', results_exam_type: 'stpm', completed_qualifications: ['spm', 'stpm'] })
    expect(sent.stpm_grades).toEqual({ PA: 'A', MATH_T: 'A' })
  })

  it('Matriculation results entered while signed out reach an account recorded SPM', async () => {
    mockApi.getProfile.mockResolvedValueOnce(SERVER_SPM as never)
    localStorage.setItem(KEY_EXAM_TYPE, 'matric')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'matric')
    localStorage.setItem(KEY_HIGHER_CGPA, '3.5')
    localStorage.setItem(KEY_HIGHER_KOKO, '8')
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    expect(mockApi.syncProfile.mock.calls[0][0]).toMatchObject({
      results_exam_type: 'matric', higher_cgpa: 3.5, completed_qualifications: ['spm', 'matric'],
    })
  })

  it('a move between two tertiary kinds is NOT sent (recency cannot be told)', async () => {
    mockApi.getProfile.mockResolvedValueOnce(
      { results_exam_type: 'stpm', completed_qualifications: ['spm', 'stpm'], results_held: 'stpm' } as never)
    localStorage.setItem(KEY_EXAM_TYPE, 'matric')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'matric')
    localStorage.setItem(KEY_HIGHER_CGPA, '3.5')
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    expect(mockApi.syncProfile.mock.calls[0][0]).not.toHaveProperty('results_exam_type')
  })
})

// Bumi coverage Sprint B (review round 3): the sign-in sync never re-sends a stale Bumiputera yes.
// After a switch to Foreign this browser holds `bumiputera: null`; a later switch back to Malaysian
// leaves it unset — so the gate must send nothing, and only a real Yes / No is ever sent.
describe('the Bumiputera answer at sign-in', () => {
  const signIn = async (demo: Record<string, unknown>) => {
    localStorage.setItem(KEY_PROFILE, JSON.stringify({ gender: 'female', ...demo }))
    render(<AuthGateModal />)
    await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
    return mockApi.syncProfile.mock.calls[0][0]
  }

  it('Malaysian -> Foreign -> Malaysian: the unset answer is not sent', async () => {
    const sent = await signIn({ nationality: 'malaysian', bumiputera: null })
    expect(sent).not.toHaveProperty('bumiputera')
  })

  it('Foreign: nothing about it is sent (the nationality makes the server store null)', async () => {
    const sent = await signIn({ nationality: 'non_malaysian', bumiputera: null })
    expect(sent).not.toHaveProperty('bumiputera')
    expect(sent.nationality).toBe('non_malaysian')
  })

  it('a real Yes / No given before sign-in is sent', async () => {
    expect((await signIn({ nationality: 'malaysian', bumiputera: true })).bumiputera).toBe(true)
  })
})
