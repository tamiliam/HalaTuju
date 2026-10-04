/**
 * THE READ PATH CARRIES THE HTTP STATUS — it did not until 2026-10-05, and every detail screen
 * in the console loads by GET.
 *
 * `adminMutate` (the WRITE path) has attached `status` and `code` to the thrown `Error` since it
 * was written, because a refused write has to be told apart from a broken one. `adminFetch` (the
 * READ path) threw a BARE `Error` with neither, so a 404 — a record that is gone, or one the
 * organisation fence refuses to admit exists — arrived at the caller indistinguishable from a
 * dropped connection. A screen could only ever say "something failed", which is why five of them
 * said four different things.
 *
 * ⚠ **IT IS TESTED THROUGH THE PUBLIC FUNCTION, NOT BY IMPORTING `adminFetch`.** The helper is
 * private to `lib/admin-api/` on purpose (its own docblock says a test reaching for it is
 * reaching past the seam), so the claim is made where callers stand: `getPartnerStudent`, one of
 * the five GETs this sprint fixed the screen for.
 */
import { getPartnerStudent } from '@/lib/admin-api'

const realFetch = global.fetch

const respond = (status: number, body: unknown) => {
  global.fetch = jest.fn(async () => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })) as unknown as typeof global.fetch
}

afterEach(() => {
  global.fetch = realFetch
  jest.restoreAllMocks()
})

it('attaches status and code to a 404 on a GET', async () => {
  respond(404, { error: 'Student not found', code: 'not_found' })
  const err = await getPartnerStudent('999999', { token: 'tok' })
    .then(() => null, (e: unknown) => e as Error & { status?: number; code?: string })
  expect(err).toBeInstanceOf(Error)
  expect(err?.status).toBe(404)
  expect(err?.code).toBe('not_found')
  // The message is unchanged — callers that only ever read `.message` are untouched.
  expect(err?.message).toBe('Student not found')
})

it('carries a 500 too, so "gone" and "broken" are distinguishable at the call site', async () => {
  // ⚠ THE POINT OF THE CHANGE. Before it, these two were the same object.
  respond(500, {})
  const err = await getPartnerStudent('7', { token: 'tok' })
    .then(() => null, (e: unknown) => e as Error & { status?: number })
  expect(err?.status).toBe(500)
  expect(err?.message).toBe('Admin API error: 500')
})

it('falls back to the server error string when no code is sent — same shape as adminMutate', async () => {
  respond(403, { error: 'org_fence' })
  const err = await getPartnerStudent('7', { token: 'tok' })
    .then(() => null, (e: unknown) => e as Error & { status?: number; code?: string })
  expect(err?.status).toBe(403)
  expect(err?.code).toBe('org_fence')
})

it('still resolves the body on a 200', async () => {
  // The floor: a guard that only ever watched the failure path would pass if the helper threw on
  // everything.
  respond(200, { supabase_user_id: 'uid-1', name: 'Test Student 07' })
  await expect(getPartnerStudent('7', { token: 'tok' }))
    .resolves.toMatchObject({ name: 'Test Student 07' })
})
