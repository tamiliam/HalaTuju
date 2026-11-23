/**
 * The captcha rule's chunk that cannot be fetched (size-fix review, 2026-11-23): a tab held across
 * a deploy, or offline. The sign-in, reset and sign-up doors get the plain "did not finish" error,
 * nothing throws, and the Supabase call is never made without a token. Its own file because the
 * module mock below throws for the whole file.
 */
import { withCaptcha } from '@/lib/captchaLazy'

jest.mock('@/lib/captchaAuth', () => {
  throw new Error('ChunkLoadError: Loading chunk 77 failed.')
})

it('returns captcha_failed, keeps the extra fields, and never makes the call', async () => {
  const call = jest.fn().mockResolvedValue({ data: {}, error: null })
  const r = await withCaptcha('sign-in', call, { data: { user: null } })
  expect(call).not.toHaveBeenCalled()
  expect(r.error).toMatchObject({ code: 'captcha_failed' })
  expect((r as unknown as { data: unknown }).data).toEqual({ user: null })
})
