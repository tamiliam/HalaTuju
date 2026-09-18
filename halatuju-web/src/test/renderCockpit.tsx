/**
 * THE COCKPIT RENDER HARNESS — mounts the REAL `view.tsx` for a given role and stage.
 *
 * ⚠ **A TEST FILE MUST NOT IMPORT `view.tsx` ITSELF — mount it through `renderCockpit`.** The
 * four `jest.mock` calls below are hoisted above the imports of THIS module, so the page loads
 * with the mocks in place. A test file that imported the page directly, ahead of this module,
 * would give it the REAL `admin-api` and every mock here would be decoration. `renderCockpit`
 * refuses to run if the registry did not take, so that mistake fails loudly rather than quietly
 * testing nothing.
 *
 * What is mocked, and why each one:
 *   * `@/lib/admin-api`  — automocked. No network. The detail fetch resolves to the fixture and
 *     every other call the screen makes ON MOUNT resolves to a sane empty value, so an
 *     unprimed call can never leave an unhandled rejection behind.
 *   * `@/lib/i18n`       — `t` echoes its key (the house pattern: `admin/spending/page.test.tsx`,
 *     `AppShell.test.tsx`, `ScholarshipDocuments.test.tsx`). Assertions read against i18n KEYS,
 *     so a copy change never breaks a cockpit test, and a key that does not resolve is caught by
 *     `src/messages/__tests__/namespaces-i18n.test.ts` instead.
 *   * `@/lib/admin-auth-context` — the signed-in officer: role + token.
 *   * `next/navigation` — `useParams()` supplies the route id; the page reads it directly.
 *
 * ⚠ **ZERO `console.error`.** A React warning (a bad key, an update outside `act`, a prop type)
 * is a defect the suite would otherwise swallow, and the cockpit is exactly where one hides.
 * `renderCockpit` installs a spy and `expectNoConsoleErrors()` — wired into an `afterEach` by
 * `installCockpitConsoleGuard()` — fails the test that produced one.
 */
import { render, type RenderResult } from '@testing-library/react'

import { AdminScholarshipDetailView } from '@/app/admin/scholarship/[id]/view'
import type { AdminRoleName } from '@/lib/navigation'
import * as adminApi from '@/lib/admin-api'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { buildApplicationDetail, type BuildOptions, type Stage } from '@/test/adminApplicationDetail'

jest.mock('@/lib/admin-api')
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => (jest.requireMock('@/lib/admin-auth-context') as {
    __cockpitAuth: { token: string | null; role: Record<string, unknown> | null }
  }).__cockpitAuth,
}))
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: '7' }),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), refresh: jest.fn() }),
  usePathname: () => '/admin/scholarship/7',
}))

const api = adminApi as jest.Mocked<typeof adminApi>

/** The mocked auth module's mutable cell — `useAdminAuth` above reads it on every render, so a
 *  test may change role between mounts without re-mocking anything. */
const authModule = jest.requireMock('@/lib/admin-auth-context') as {
  __cockpitAuth: { token: string | null; role: Record<string, unknown> | null }
}
authModule.__cockpitAuth = { token: 'test-token', role: null }

/** The reviewer the fixture assigns cases to (`assigned_to_id: 42`). A role given this id is the
 *  admin who HOLDS the case, which is what `canWrite` and the self-QC guard both turn on. */
export const ASSIGNED_ADMIN_ID = 42

export interface CockpitAuth {
  role: AdminRoleName
  /** The signed-in admin's own id. Defaults to `ASSIGNED_ADMIN_ID` for a reviewer/admin (so they
   *  hold the case and may write) and to a DIFFERENT id for qc/org_admin (so the two-person
   *  control is not self-tripped). */
  adminId?: number | null
  token?: string | null
}

/** The id a QC or org_admin signs in as by default — deliberately NOT the assignee's, because a
 *  `qc` who reviewed the case may not QC it (the cockpit hides the panel; the backend refuses). */
export const OTHER_ADMIN_ID = 43

function authFor({ role, adminId, token = 'test-token' }: CockpitAuth) {
  const own = adminId !== undefined
    ? adminId
    : (role === 'reviewer' || role === 'admin' ? ASSIGNED_ADMIN_ID : OTHER_ADMIN_ID)
  return {
    token,
    role: {
      is_admin: true,
      is_super_admin: role === 'super',
      role,
      admin_id: own,
      admin_name: 'Test Officer 04',
      org_name: 'Test Organisation',
      owning_org_id: 11,
      owning_org_name: 'Test Organisation',
      reviewer_profile_complete: true,
    },
  }
}

/**
 * Every admin-api call the cockpit makes ON MOUNT, primed with a sane empty answer.
 *
 * ⚠ The automock returns `undefined`, and `undefined.then` is a TypeError inside a `useEffect` —
 * which React reports as an error on a background microtask, not as a failed assertion. Priming
 * all four is what keeps an unprimed call from becoming a mystery.
 */
export function primeCockpitApi(app: AdminScholarshipDetail): void {
  api.getScholarshipApplication.mockResolvedValue(app)
  api.getAssignableAdmins.mockResolvedValue({ admins: [
    { id: ASSIGNED_ADMIN_ID, name: 'Test Reviewer 01', role: 'reviewer',
      email: 'reviewer@example.test', languages: ['en'], corrections: 0, paused: false,
      programme_id: null, programme_name: '' },
    { id: OTHER_ADMIN_ID, name: 'Test Reviewer 05', role: 'reviewer',
      email: 'reviewer05@example.test', languages: ['en'], corrections: 0, paused: false,
      programme_id: null, programme_name: '' },
  ] })
  api.getVerdictCaseSummary.mockResolvedValue({ enabled: false })
  api.getSources.mockResolvedValue({ sources: [], programmes: [] })
}

export interface CockpitOptions extends CockpitAuth {
  /** The stage to build, when no `app` is supplied. */
  stage?: Stage
  /** Field overrides (and the `outcome` road) handed to `buildApplicationDetail`. */
  build?: BuildOptions
  /** A payload built by hand, instead of `stage` + `build`. */
  app?: AdminScholarshipDetail
}

export interface MountedCockpit extends RenderResult {
  app: AdminScholarshipDetail
  api: jest.Mocked<typeof adminApi>
}

/**
 * Mount the cockpit. Returns the Testing Library result plus the payload it was given, so an
 * assertion can name a value the fixture chose without re-deriving it.
 *
 * The caller still awaits something (`findBy*`): the detail arrives through a promise, so the
 * first paint is the loading line and nothing is on screen until it resolves.
 */
export function renderCockpit(options: CockpitOptions): MountedCockpit {
  if (!jest.isMockFunction(api.getScholarshipApplication)) {
    throw new Error(
      'renderCockpit: @/lib/admin-api is not mocked. Import "@/test/renderCockpit" BEFORE '
      + '"./view" in the test file — the mocks are hoisted into this module, and the page '
      + 'captures the real functions if it loads first.')
  }
  const app = options.app
    ?? buildApplicationDetail(options.stage ?? 'interviewing', options.build ?? {})
  authModule.__cockpitAuth = authFor(options)
  primeCockpitApi(app)
  const result = render(<AdminScholarshipDetailView />)
  return Object.assign(result, { app, api })
}

// ── The console guard ────────────────────────────────────────────────────────────────────────
let consoleSpy: jest.SpyInstance | null = null

/** Start recording `console.error`. Called from `installCockpitConsoleGuard`'s `beforeEach`. */
export function startCockpitConsoleGuard(): void {
  consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
}

/**
 * Fail with the first message if anything wrote to `console.error` during the test.
 *
 * ⚠ IT REFUSES TO PASS WHEN NO SPY WAS INSTALLED. A guard that returns quietly because its own
 * set-up did not run is the decorative-test shape this sprint exists to retire; the harness must
 * fail loudly instead of reporting a clean run it never watched.
 */
export function expectNoConsoleErrors(): void {
  const spy = consoleSpy
  consoleSpy = null
  if (!spy) {
    throw new Error(
      'expectNoConsoleErrors: no console spy was installed, so nothing was watched. Call '
      + 'installCockpitConsoleGuard() once at the top of the test file.')
  }
  const calls = spy.mock.calls.slice()
  spy.mockRestore()
  if (calls.length > 0) {
    throw new Error(
      'The cockpit wrote to console.error, which means React reported a defect this test would '
      + `otherwise have swallowed:\n${calls.map((c) => c.map(String).join(' ')).join('\n')}`)
  }
}

/**
 * Wire the console guard and the mock reset into one `describe`. Call it once at the top of a
 * cockpit test file.
 */
export function installCockpitConsoleGuard(): void {
  beforeEach(() => {
    jest.clearAllMocks()
    startCockpitConsoleGuard()
  })
  afterEach(() => {
    expectNoConsoleErrors()
  })
}
