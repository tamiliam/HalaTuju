/**
 * CAPTCHA REPAIR (2026-11-19) — the password doors never call Supabase without a token.
 *
 * Supabase's captcha switch is ON. Before the repair, a Turnstile fetch that failed resolved to
 * `undefined`, every door then called Supabase with no token, and the visitor read Supabase's raw
 * "captcha protection: request disallowed". Pinned here for each door (admin sign-in, admin reset,
 * sponsor sign-in, sponsor sign-up, sponsor reset):
 *   - blocked / failed → a known error code, and Supabase is NOT called;
 *   - ok → Supabase is called WITH the token;
 *   - Supabase still refuses the captcha → one fresh token, one more try, then `captcha_failed`;
 *   - off (no site key: local dev) → called without a token, as before;
 *   - any other error passes through untouched (the screen's own handling).
 * And the words: en / ms / ta hold them, and the screen text never carries the raw Supabase words.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import type { TurnstileFetchOptions, TurnstileResult } from '@/lib/turnstile'

const getTurnstileResult = jest.fn<Promise<TurnstileResult>, [string?, TurnstileFetchOptions?]>()
jest.mock('@/lib/turnstile', () => ({
  getTurnstileResult: (a?: string, o?: TurnstileFetchOptions) => getTurnstileResult(a, o),
  getTurnstileToken: jest.fn(),
}))

const auth = {
  signInWithPassword: jest.fn(),
  signUp: jest.fn(),
  resetPasswordForEmail: jest.fn(),
}
jest.mock('@/lib/supabaseAuthClient', () => ({ createAuthOnlyClient: () => ({ auth }) }))
jest.mock('@/lib/topBanner', () => ({ clearSignInDismissals: jest.fn() }))

import { adminResetPassword, adminSignInWithPassword } from '@/lib/admin-supabase'
import {
  sponsorResetPassword, sponsorSignInWithPassword, sponsorSignUpWithPassword,
} from '@/lib/sponsor-supabase'
import { captchaCodeOf, captchaErrorText } from '@/lib/captchaAuth'

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://example.supabase.co'
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'anon-key'

const RAW = 'captcha protection: request disallowed (timeout-or-duplicate)'
const refusal = { error: { code: 'captcha_failed', message: RAW, status: 400 }, data: { user: null, session: null } }

type Door = {
  name: string
  run: () => Promise<{ error: unknown }>
  sb: jest.Mock
  tokenOf: (call: unknown[]) => unknown
}
const DOORS: Door[] = [
  { name: 'admin sign-in', run: () => adminSignInWithPassword('a@x.org', 'pw'), sb: auth.signInWithPassword,
    tokenOf: (c) => (c[0] as { options?: { captchaToken?: string } }).options?.captchaToken },
  { name: 'admin reset', run: () => adminResetPassword('a@x.org'), sb: auth.resetPasswordForEmail,
    tokenOf: (c) => (c[1] as { captchaToken?: string }).captchaToken },
  { name: 'sponsor sign-in', run: () => sponsorSignInWithPassword('s@x.org', 'pw'), sb: auth.signInWithPassword,
    tokenOf: (c) => (c[0] as { options?: { captchaToken?: string } }).options?.captchaToken },
  { name: 'sponsor sign-up', run: () => sponsorSignUpWithPassword('s@x.org', 'pw', 'Name'), sb: auth.signUp,
    tokenOf: (c) => (c[0] as { options: { captchaToken?: string } }).options.captchaToken },
  { name: 'sponsor reset', run: () => sponsorResetPassword('s@x.org'), sb: auth.resetPasswordForEmail,
    tokenOf: (c) => (c[1] as { captchaToken?: string }).captchaToken },
]

beforeEach(() => {
  getTurnstileResult.mockReset()
  Object.values(auth).forEach((f) => f.mockReset().mockResolvedValue({ data: { user: null, session: null }, error: null }))
  ;(global as unknown as { window: unknown }).window = { location: { origin: 'https://halatuju.xyz' } }
})

describe.each(DOORS)('$name', ({ run, sb, tokenOf }) => {
  it('blocked: returns captcha_blocked and never calls Supabase', async () => {
    getTurnstileResult.mockResolvedValue({ status: 'blocked' })
    const { error } = await run()
    expect((error as { code: string }).code).toBe('captcha_blocked')
    expect(sb).not.toHaveBeenCalled()
  })

  it('failed: returns captcha_failed and never calls Supabase', async () => {
    getTurnstileResult.mockResolvedValue({ status: 'failed' })
    const { error } = await run()
    expect((error as { code: string }).code).toBe('captcha_failed')
    expect(sb).not.toHaveBeenCalled()
  })

  it('ok: calls Supabase with the token', async () => {
    getTurnstileResult.mockResolvedValue({ status: 'ok', token: 'tok-1' })
    const { error } = await run()
    expect(error).toBeNull()
    expect(sb).toHaveBeenCalledTimes(1)
    expect(tokenOf(sb.mock.calls[0])).toBe('tok-1')
  })

  it('a captcha refusal (lapsed or duplicate token) gets ONE fresh token and one more try', async () => {
    getTurnstileResult
      .mockResolvedValueOnce({ status: 'ok', token: 'tok-1' })
      .mockResolvedValueOnce({ status: 'ok', token: 'tok-2' })
    sb.mockResolvedValueOnce(refusal)
    const { error } = await run()
    expect(error).toBeNull()
    expect(sb).toHaveBeenCalledTimes(2)
    expect(tokenOf(sb.mock.calls[1])).toBe('tok-2')
  })

  it('the retry is capped: the first fetch is a full round, the retry ONE attempt', async () => {
    getTurnstileResult.mockResolvedValue({ status: 'ok', token: 'tok' })
    sb.mockResolvedValue(refusal)
    await run()
    expect(getTurnstileResult).toHaveBeenCalledTimes(2)
    expect(getTurnstileResult.mock.calls[0][1]).toBeUndefined()
    expect(getTurnstileResult.mock.calls[1][1]).toEqual({ maxAttempts: 1 })
  })

  it('no site key but Supabase refuses (switch on, key missing): a console warning, plain words, one call', async () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => undefined)
    try {
      getTurnstileResult.mockResolvedValue({ status: 'off' })
      sb.mockResolvedValue(refusal)
      const { error } = await run()
      expect((error as { code: string }).code).toBe('captcha_failed')
      expect(sb).toHaveBeenCalledTimes(1)
      expect(warn).toHaveBeenCalledTimes(1)
      expect(String(warn.mock.calls[0][0])).toMatch(/site key/)
    } finally {
      warn.mockRestore()
    }
  })

  it('refused twice: captcha_failed, never the raw Supabase words', async () => {
    getTurnstileResult.mockResolvedValue({ status: 'ok', token: 'tok' })
    sb.mockResolvedValue(refusal)
    const { error } = await run()
    expect((error as { code: string }).code).toBe('captcha_failed')
    expect((error as { message: string }).message).not.toMatch(/captcha protection/)
    expect(sb).toHaveBeenCalledTimes(2)
  })

  it('off (no site key, local dev): calls Supabase without a token, as before', async () => {
    getTurnstileResult.mockResolvedValue({ status: 'off' })
    await run()
    expect(sb).toHaveBeenCalledTimes(1)
    expect(tokenOf(sb.mock.calls[0])).toBeUndefined()
  })

  it('any other error passes through untouched', async () => {
    getTurnstileResult.mockResolvedValue({ status: 'ok', token: 'tok' })
    const other = { message: 'Invalid login credentials', code: 'invalid_credentials', status: 400 }
    sb.mockResolvedValue({ data: { user: null, session: null }, error: other })
    const { error } = await run()
    expect(error).toBe(other)
    expect(sb).toHaveBeenCalledTimes(1)
  })
})

describe('the words', () => {
  // The words sit in the slice each door already loads, not in the core catalogue every route
  // downloads: sponsorAuth.captcha* for the sponsor doors, admin.loginCaptcha.* for the admin doors.
  type Bag = Record<string, string>
  const sponsorOf = (m: unknown) => (m as { sponsorAuth: Bag }).sponsorAuth
  const adminOf = (m: unknown) => (m as { admin: { loginCaptcha: Bag } }).admin.loginCaptcha
  const pairs: Array<[string, (m: unknown) => Bag, readonly string[]]> = [
    ['sponsorAuth', sponsorOf, ['captchaBlocked', 'captchaFailed', 'captchaGoogle']],
    ['admin.loginCaptcha', adminOf, ['blocked', 'failed', 'google']],
  ]

  it.each(pairs)('%s holds every captcha line in en, ms and ta', (_n, bag, keys) => {
    for (const m of [en, ms, ta]) {
      for (const k of keys) {
        expect(typeof bag(m)[k]).toBe('string')
        expect(bag(m)[k].trim().length).toBeGreaterThan(0)
        expect(bag(m)[k]).not.toMatch(/captcha/i)
      }
    }
  })

  it('the core catalogue no longer carries them', () => {
    for (const m of [en, ms, ta]) {
      expect((m as unknown as { errors: Bag }).errors.captchaBlocked).toBeUndefined()
    }
  })

  it.each(pairs)('%s: Malay and Tamil are translated, not copies of the English', (_n, bag, keys) => {
    for (const k of keys.slice(0, 2)) {
      expect(bag(ms)[k]).not.toBe(bag(en)[k])
      expect(bag(ta)[k]).not.toBe(bag(en)[k])
    }
  })

  it.each(pairs)('%s: the English says what to try: ad blocker, another browser, mobile data', (_n, bag, keys) => {
    for (const k of keys.slice(0, 2)) {
      expect(bag(en)[k]).toMatch(/ad blocker/)
      expect(bag(en)[k]).toMatch(/another browser/)
      expect(bag(en)[k]).toMatch(/mobile data/)
    }
    expect(bag(en)[keys[2]]).toMatch(/Google/)
  })

  it.each([['admin' as const, adminOf(en)], ['sponsor' as const, sponsorOf(en)]])(
    '%s: maps each failure to its words; the Google line only where the door offers Google', (scope, _bag) => {
      const w = scope === 'admin'
        ? { b: adminOf(en).blocked, f: adminOf(en).failed, g: adminOf(en).google }
        : { b: sponsorOf(en).captchaBlocked, f: sponsorOf(en).captchaFailed, g: sponsorOf(en).captchaGoogle }
      const words = { blocked: w.b, failed: w.f, google: w.g }
      expect(captchaErrorText({ code: 'captcha_blocked' }, words, false)).toBe(w.b)
      expect(captchaErrorText({ code: 'captcha_failed' }, words, true)).toBe(`${w.f} ${w.g}`)
      expect(captchaCodeOf({ message: RAW, status: 400 })).toBe('captcha_failed')
      expect(captchaErrorText({ message: RAW }, words, false)).toBe(w.f)
    })

  it('leaves every other error to the screen', () => {
    const words = { blocked: 'b', failed: 'f', google: 'g' }
    expect(captchaErrorText({ message: 'Invalid login credentials' }, words, true)).toBeNull()
    expect(captchaErrorText(null, words, true)).toBeNull()
  })
})
