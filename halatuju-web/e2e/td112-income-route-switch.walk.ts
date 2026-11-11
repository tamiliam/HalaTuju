/**
 * TD-112 walk — the self-serve income route switch in the Action Centre (audit sprint A4.6).
 *
 * ⚠ SKIPPED BY DEFAULT. The switch lives on a signed-in student's application page and posts to
 * `.../income-route/`, which reads the student from their Supabase session and changes their real
 * application. Faking that would test the fake, so the walk runs only in full-stack mode
 * (hermetic.ts), against a LOCAL Supabase and a LOCAL API holding a made-up student:
 *
 *   WALK_STUDENT_EMAIL / WALK_STUDENT_PASSWORD   a made-up local student whose application is
 *                                                profile_complete on the STR route with an income task
 *
 * The student is signed in by asking the LOCAL Supabase for a session with that password and placing
 * it where the app's student client keeps it (lib/supabaseAuthClient.ts `defaultStorageKey`). The
 * walk switches to the salary route, checks the page took it, then switches back so the made-up
 * student is left as it was.
 */
import { test, expect } from '@playwright/test'
import { FULL_STACK_SKIP_REASON, appSupabaseKey, appSupabaseUrl, fullStack, say, seal } from './hermetic'

const env = process.env
test.skip(!fullStack() || !env.WALK_STUDENT_EMAIL || !env.WALK_STUDENT_PASSWORD,
  `TD-112 ${FULL_STACK_SKIP_REASON} Also set WALK_STUDENT_EMAIL and WALK_STUDENT_PASSWORD.`)

const sw = (k: string) => say('en', `scholarship.incomeRouteSwitch.${k}`)

test('a student switches from STR to salary and back', async ({ page, context, request }) => {
  await seal(context)
  const res = await request.post(`${appSupabaseUrl()}/auth/v1/token?grant_type=password`, {
    headers: { apikey: appSupabaseKey() },
    data: { email: env.WALK_STUDENT_EMAIL, password: env.WALK_STUDENT_PASSWORD },
  })
  expect(res.ok()).toBeTruthy()
  const session = await res.json()
  // Same rule as defaultStorageKey(): sb-<first label of the Supabase host>-auth-token.
  const key = `sb-${new URL(appSupabaseUrl()).hostname.split('.')[0]}-auth-token`
  await context.addInitScript(([k, v]) => { window.localStorage.setItem(k, v) }, [key, JSON.stringify(session)])

  await page.goto('/scholarship/application')
  const open = page.getByRole('button', { name: sw('cta') })
  await expect(open).toBeVisible({ timeout: 60_000 })

  // STR → salary, the father works.
  await open.click()
  await page.getByRole('button', { name: sw('route.salary') }).click()
  await page.getByRole('button', { name: sw('member.father'), exact: true }).click()
  await page.getByRole('button', { name: sw('confirm') }).click()
  await expect(page.getByText(sw('error'))).toHaveCount(0)
  await expect(page.getByRole('button', { name: sw('cta') })).toBeVisible({ timeout: 60_000 })

  // And back: salary → STR in the father's name, so the made-up student ends as it began.
  await page.getByRole('button', { name: sw('cta') }).click()
  await page.getByRole('button', { name: sw('route.str') }).click()
  await page.getByRole('button', { name: sw('member.father'), exact: true }).click()
  await page.getByRole('button', { name: sw('confirm') }).click()
  await expect(page.getByText(sw('error'))).toHaveCount(0)
  await expect(page.getByRole('button', { name: sw('cta') })).toBeVisible({ timeout: 60_000 })
})
