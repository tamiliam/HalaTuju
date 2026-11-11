/**
 * TD-070 walk — sponsor sign-in and the admin vetting buttons (audit sprint A4.6).
 *
 * ⚠ SKIPPED BY DEFAULT. Both halves need a REAL sign-in: the sponsor signs in through Supabase and
 * the API then reads who they are; the admin side needs a signed-in admin of the sponsor's
 * programme. Faking the Supabase answers would only prove the fake, which is the very gap TD-070
 * records. So the walk runs only in full-stack mode (hermetic.ts), against a LOCAL Supabase and a
 * LOCAL API holding made-up accounts:
 *
 *   WALK_SPONSOR_EMAIL / WALK_SPONSOR_PASSWORD   a made-up sponsor (status pending is fine)
 *   WALK_ADMIN_EMAIL / WALK_ADMIN_PASSWORD       a made-up admin who may vet that sponsor
 *   WALK_VIEWER_EMAIL / WALK_VIEWER_PASSWORD     optional: a made-up viewer, who must see no buttons
 *
 * Out of reach even then, and left to the owner: the Google round trip and the real project's
 * email-confirmation setting.
 */
import { test, expect, type Page } from '@playwright/test'
import { FULL_STACK_SKIP_REASON, fullStack, say, seal } from './hermetic'

const env = process.env
const haveAccounts = Boolean(env.WALK_SPONSOR_EMAIL && env.WALK_SPONSOR_PASSWORD && env.WALK_ADMIN_EMAIL && env.WALK_ADMIN_PASSWORD)

test.skip(!fullStack() || !haveAccounts, `TD-070 ${FULL_STACK_SKIP_REASON} Also set WALK_SPONSOR_* and WALK_ADMIN_*.`)

async function signIn(page: Page, path: string, email: string, password: string, submit: string) {
  await page.goto(path)
  await page.locator('input[type="email"]').first().fill(email)
  await page.locator('input[type="password"]').first().fill(password)
  await page.getByRole('button', { name: submit }).click()
}

test('a sponsor signs in with email and password and lands in the portal', async ({ page, context }) => {
  await seal(context)
  await signIn(page, '/sponsor/login', env.WALK_SPONSOR_EMAIL!, env.WALK_SPONSOR_PASSWORD!, say('en', 'sponsorAuth.signIn'))
  await expect(page).toHaveURL(/\/sponsor(\/|$)/, { timeout: 60_000 })
  // Signed in: never the public landing again. A pending sponsor sees the waiting screen; an
  // approved one sees the portal.
  await expect(page.getByRole('heading', { name: say('en', 'sponsorLanding.hero.heading') })).toHaveCount(0)
})

test('an admin opens the sponsor and the vetting button flips', async ({ page, context }) => {
  await seal(context)
  await signIn(page, '/admin/login', env.WALK_ADMIN_EMAIL!, env.WALK_ADMIN_PASSWORD!, say('en', 'admin.signIn'))
  await page.waitForURL(/\/admin(\/|$)/, { timeout: 60_000 })
  await page.goto('/admin/sponsors')
  await page.getByRole('link', { name: new RegExp(env.WALK_SPONSOR_EMAIL!.split('@')[0], 'i') }).first().click()
  const accept = page.getByRole('button', { name: say('en', 'admin.sponsors.detail.giftAccept') }).first()
  const takeBack = page.getByRole('button', { name: say('en', 'admin.sponsors.detail.giftTakeBack') }).first()
  await expect(accept.or(takeBack)).toBeVisible({ timeout: 60_000 })
  if (await accept.isVisible()) {
    await accept.click()
    await expect(takeBack).toBeVisible()
  }
  await takeBack.click()                 // put it back the way it was
  await expect(accept).toBeVisible()
})

test('a viewer sees the sponsor but no vetting buttons', async ({ page, context }) => {
  test.skip(!env.WALK_VIEWER_EMAIL || !env.WALK_VIEWER_PASSWORD, 'no made-up viewer account given (WALK_VIEWER_*)')
  await seal(context)
  await signIn(page, '/admin/login', env.WALK_VIEWER_EMAIL!, env.WALK_VIEWER_PASSWORD!, say('en', 'admin.signIn'))
  await page.waitForURL(/\/admin(\/|$)/, { timeout: 60_000 })
  await page.goto('/admin/sponsors')
  await page.getByRole('link', { name: new RegExp(env.WALK_SPONSOR_EMAIL!.split('@')[0], 'i') }).first().click()
  await expect(page.getByRole('button', { name: say('en', 'admin.sponsors.detail.giftAccept') })).toHaveCount(0)
  await expect(page.getByRole('button', { name: say('en', 'admin.sponsors.detail.giftTakeBack') })).toHaveCount(0)
})
