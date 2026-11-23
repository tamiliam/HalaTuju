/**
 * CAPTCHA FOR THE PASSWORD DOORS — captcha repair, 2026-11-19.
 *
 * Supabase's captcha switch is ON, so every password sign-in, sponsor sign-up and password
 * reset must carry a Turnstile token. This module is the one place that rule is kept:
 *
 *   1. Fetch a token (`getTurnstileResult`). `blocked` / `failed` → return a known error code
 *      and DO NOT call Supabase (a token-less call can only come back as Supabase's raw
 *      "captcha protection: request disallowed"). `off` (no site key: local dev) → call without
 *      a token, as before.
 *   2. Call Supabase with the token.
 *   3. If Supabase still refuses the captcha (the token lapsed in flight, or was already used),
 *      fetch ONE fresh token — a single attempt (`maxAttempts: 1`), not a second full round — and
 *      call once more. A second refusal returns `captcha_failed`, so the raw Supabase words never
 *      reach the screen. A refusal with NO site key (switch on, key missing from the build) logs a
 *      console warning, so the deploy mistake is visible.
 *
 * The screens turn the codes into plain words with `captchaErrorKeys()` (en/ms/ta in
 * `messages/*.json`, `admin.loginCaptcha.*` / `sponsorAuth.captcha*`). Google sign-in does not pass through here: OAuth
 * redirects carry no captcha.
 */
import { getTurnstileResult } from '@/lib/turnstile'

export type CaptchaErrorCode = 'captcha_blocked' | 'captcha_failed'

/** The error a door returns when the security check could not be passed. Shaped like a
 *  Supabase AuthError (`message`, `code`, `status`, `name`) so a screen's existing
 *  `error.message` handling still has something sane to read. */
export interface CaptchaError {
  name: 'CaptchaError'
  code: CaptchaErrorCode
  status: 0
  message: string
}

export function captchaError(code: CaptchaErrorCode): CaptchaError {
  return {
    name: 'CaptchaError',
    code,
    status: 0,
    message: code === 'captcha_blocked'
      ? 'The security check could not load.'
      : 'The security check did not finish.',
  }
}

/** True when Supabase refused the request over the captcha (its code is `captcha_failed`,
 *  its words "captcha protection: request disallowed (...)"). */
export function isSupabaseCaptchaRefusal(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const e = error as { code?: unknown; message?: unknown }
  if (e.code === 'captcha_failed') return true
  return typeof e.message === 'string' && /captcha/i.test(e.message)
}

/** The code of a door's error when it is a captcha failure, else null. */
export function captchaCodeOf(error: unknown): CaptchaErrorCode | null {
  if (!error || typeof error !== 'object') return null
  const code = (error as { code?: unknown }).code
  if (code === 'captcha_blocked' || code === 'captcha_failed') return code
  return isSupabaseCaptchaRefusal(error) ? 'captcha_failed' : null
}

/**
 * Run a Supabase auth call behind the captcha rule above. `call` receives the token
 * (`undefined` only when Turnstile is not configured) and must return `{ error }` at least.
 * On a captcha failure the result is `{ ...onCaptchaError, error: CaptchaError }`.
 */
export async function withCaptcha<R extends { error: unknown }>(
  action: string,
  call: (captchaToken: string | undefined) => Promise<R>,
  onCaptchaError: Omit<R, 'error'>,
): Promise<R | (Omit<R, 'error'> & { error: CaptchaError })> {
  for (let round = 0; round < 2; round++) {
    // The retry after a refusal gets ONE attempt, not a second full round (review fix):
    // worst-case waits are written in lib/turnstile.ts and turnstile-rollout.md.
    const t = await getTurnstileResult(action, round === 0 ? undefined : { maxAttempts: 1 })
    if (t.status === 'blocked') return { ...onCaptchaError, error: captchaError('captcha_blocked') }
    if (t.status === 'failed') return { ...onCaptchaError, error: captchaError('captcha_failed') }
    const result = await call(t.status === 'ok' ? t.token : undefined)
    if (!isSupabaseCaptchaRefusal(result.error)) return result
    // Refused without a token: the site key is missing from this build while Supabase's captcha
    // switch is on — a deploy mistake, and a retry cannot help. Say so in the console (no secrets)
    // so it is visible; the visitor still gets the plain "did not finish" words.
    if (t.status === 'off') {
      console.warn('[captcha] Supabase refused a request for want of a captcha token, but no Turnstile '
        + 'site key is set in this build (NEXT_PUBLIC_TURNSTILE_SITE_KEY). Set it and redeploy the web app.')
      break
    }
  }
  return { ...onCaptchaError, error: captchaError('captcha_failed') }
}

/**
 * The words a screen shows for a captcha failure: the main sentence, plus the "sign in with
 * Google" line only where that screen offers Google. Null when `error` is not a captcha failure
 * (the screen keeps its own handling). `t` is the screen's `useT()`.
 */
export type CaptchaWords = { blocked: string; failed: string; google: string }

export function captchaErrorText(
  error: unknown,
  words: CaptchaWords,
  offersGoogle: boolean,
): string | null {
  const code = captchaCodeOf(error)
  if (!code) return null
  // The screen reads its own words (`admin.loginCaptcha.*` or `sponsorAuth.captcha*`) from the slice it
  // already loads and hands them in; this module holds no catalogue key, so it rides no route's slice.
  const main = code === 'captcha_blocked' ? words.blocked : words.failed
  return offersGoogle ? `${main} ${words.google}` : main
}
