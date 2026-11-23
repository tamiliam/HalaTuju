/**
 * `withCaptcha` behind a dynamic import, for the two Supabase door modules (`admin-supabase.ts`,
 * `sponsor-supabase.ts`).
 *
 * Those modules ride on every admin and sponsor route (the auth context imports them), but the
 * captcha rule (`captchaAuth.ts`, with the Turnstile client behind it) only runs when someone
 * actually signs in, resets a password or registers. Importing it statically put ~1 kB of
 * first-load JavaScript on every one of those routes and pushed the median route and the case
 * page over their budget (2026-11-23). Behaviour is unchanged: same function, fetched on first use.
 */
import type { withCaptcha as WithCaptcha } from '@/lib/captchaAuth'

export const withCaptcha: typeof WithCaptcha = async (action, call, onCaptchaError) => {
  const m = await import('@/lib/captchaAuth')
  return m.withCaptcha(action, call, onCaptchaError)
}
