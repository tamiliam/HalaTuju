/**
 * @jest-environment jsdom
 *
 * CAPTCHA REPAIR (2026-11-19) — no anonymous "guest" session on page load.
 *
 * The AuthProvider used to call `signInAnonymously()` on every page load with no session: a
 * Turnstile challenge and a Supabase auth row per visitor, and — with the captcha switch on — a
 * failure for anyone whose browser blocks Cloudflare. Nothing reads the anonymous session (the
 * API ignores anonymous tokens; every student screen treats "no session" as "anonymous"), so it
 * is not created at all. Pinned here:
 *   - a visitor with no session finishes loading as 'anonymous', with no token and no session;
 *   - no Turnstile fetch and no Supabase anonymous sign-in happens on any student route;
 *   - no production source calls `signInAnonymously` any more;
 *   - a browser that already holds an anonymous session keeps working as before.
 */
import * as fs from 'fs'
import * as path from 'path'
import { render, waitFor } from '@testing-library/react'

import { AuthProvider, useAuth } from '@/lib/auth-context'

let mockPath = '/'
jest.mock('next/navigation', () => ({
  usePathname: () => mockPath,
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}))

let mockSession: unknown = null
const supabaseAnon = jest.fn()
jest.mock('@/lib/supabase', () => ({
  getSession: () => Promise.resolve({ session: mockSession }),
  getSupabase: () => ({
    auth: {
      signInAnonymously: (...a: unknown[]) => supabaseAnon(...a),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: jest.fn() } } }),
    },
  }),
}))
const turnstile = jest.fn()
jest.mock('@/lib/turnstile', () => ({
  getTurnstileResult: (...a: unknown[]) => turnstile(...a),
  getTurnstileToken: (...a: unknown[]) => turnstile(...a),
  isTurnstileConfigured: () => true,
}))
const getProfile = jest.fn(() => Promise.resolve({ nric: null }))
jest.mock('@/lib/api', () => ({ getProfile: () => getProfile() }))

type Seen = ReturnType<typeof useAuth>
let last: Seen | null = null
function Probe() { last = useAuth(); return null }

beforeEach(() => {
  localStorage.clear()
  mockSession = null
  last = null
  supabaseAnon.mockClear(); turnstile.mockClear(); getProfile.mockClear()
})

describe('no anonymous session is minted on page load', () => {
  it.each(['/', '/dashboard', '/onboarding/grades', '/quiz', '/search', '/course/abc'])(
    'a visitor with no session on %s: loads as anonymous, no Turnstile, no anonymous sign-in', async (p) => {
      mockPath = p
      render(<AuthProvider><Probe /></AuthProvider>)
      await waitFor(() => expect(last?.isLoading).toBe(false))
      expect(last?.status).toBe('anonymous')
      expect(last?.hasSession).toBe(false)
      expect(last?.isAnonymous).toBe(true)
      expect(last?.token).toBeNull()
      expect(last?.isAuthenticated).toBe(false)
      expect(supabaseAnon).not.toHaveBeenCalled()
      expect(turnstile).not.toHaveBeenCalled()
      expect(getProfile).not.toHaveBeenCalled()
    })

  it('a browser that already holds an anonymous session keeps it, as before', async () => {
    mockSession = { access_token: 'anon-tkn', user: { id: 'anon-1', is_anonymous: true } }
    render(<AuthProvider><Probe /></AuthProvider>)
    await waitFor(() => expect(last?.isLoading).toBe(false))
    expect(last?.status).toBe('anonymous')
    expect(last?.hasSession).toBe(true)
    expect(last?.isAnonymous).toBe(true)
    expect(supabaseAnon).not.toHaveBeenCalled()
    expect(turnstile).not.toHaveBeenCalled()
  })

  it('a signed-in student is unchanged: profile read, no captcha', async () => {
    mockSession = { access_token: 'tkn', user: { id: 'u1', is_anonymous: false } }
    render(<AuthProvider><Probe /></AuthProvider>)
    await waitFor(() => expect(last?.isLoading).toBe(false))
    expect(getProfile).toHaveBeenCalled()
    expect(last?.status).toBe('needs-nric')
    expect(turnstile).not.toHaveBeenCalled()
  })
})

describe('nothing in the app mints an anonymous session any more', () => {
  const SRC = path.join(__dirname, '..', '..')
  const files: string[] = []
  const walk = (dir: string) => fs.readdirSync(dir, { withFileTypes: true }).forEach((e) => {
    const full = path.join(dir, e.name)
    if (e.isDirectory()) { if (e.name !== '__tests__' && e.name !== 'node_modules') walk(full) }
    else if (/\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name)) files.push(full)
  })
  walk(SRC)

  it('no production source calls signInAnonymously', () => {
    const callers = files.filter((f) => /signInAnonymously\s*\(/.test(fs.readFileSync(f, 'utf8')))
    expect(callers).toEqual([])
  })

  it('lib/supabase no longer exports it', () => {
    const src = fs.readFileSync(path.join(SRC, 'lib', 'supabase.ts'), 'utf8')
    expect(src).not.toMatch(/export async function signInAnonymously/)
  })
})
