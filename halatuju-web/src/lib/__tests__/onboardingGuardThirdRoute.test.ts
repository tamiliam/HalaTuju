/**
 * @jest-environment jsdom
 *
 * Third results route S2b — a Matriculation / Asasi / Diploma CGPA is a result on its own, so the
 * onboarding guard lets its holder in. Without it, a student who had just finished the third-route
 * form (no SPM `grades`, no STPM grades — her SPM block lives in `spm_prereq_grades`) was sent back
 * to "Choose Your Exam" by every guarded page.
 */
import { useOnboardingGuard } from '@/lib/useOnboardingGuard'
import { KEY_HIGHER_CGPA } from '@/lib/storage'

let mockAuth: { status: string; profile: Record<string, unknown> | null } = { status: 'ready', profile: null }
jest.mock('@/lib/auth-context', () => ({ useAuth: () => mockAuth }))

beforeEach(() => localStorage.clear())

it('a signed-in holder of a third-route CGPA is onboarded', () => {
  mockAuth = { status: 'ready', profile: { grades: {}, stpm_grades: {}, higher_cgpa: 3.2 } }
  expect(useOnboardingGuard().ready).toBe(true)
})

it('an anonymous browser holding a third-route CGPA is onboarded', () => {
  mockAuth = { status: 'anonymous', profile: null }
  localStorage.setItem(KEY_HIGHER_CGPA, '2.8')
  expect(useOnboardingGuard().ready).toBe(true)
})

it('nothing at all is still not onboarded (positive control)', () => {
  mockAuth = { status: 'ready', profile: { grades: {}, stpm_grades: {}, higher_cgpa: null } }
  expect(useOnboardingGuard().ready).toBe(false)
  mockAuth = { status: 'anonymous', profile: null }
  expect(useOnboardingGuard().ready).toBe(false)
})
