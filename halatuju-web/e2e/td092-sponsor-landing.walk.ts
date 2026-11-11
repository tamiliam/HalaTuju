/**
 * TD-092 walk — the public sponsor landing, in English, Malay and Tamil (audit sprint A4.6).
 *
 * A signed-out visitor opens /sponsor and gets the marketing landing. For each locale the walk checks
 * that the hero heading and the call to action are in that language, that the "students waiting"
 * counter shows the number the count endpoint gave (and is absent at zero), and that "Become a
 * sponsor" opens the sign-up page in the same language.
 *
 * Hermetic: the count endpoint is answered with a made-up number, every other API call is 404,
 * and anything off this machine is blocked (see hermetic.ts). No live site, no accounts, no email.
 */
import { test, expect } from '@playwright/test'
import { LOCALES, say, seal, useLocale } from './hermetic'

const COUNT_PATH = '/api/v1/sponsor/pool/count/'

for (const locale of LOCALES) {
  test(`sponsor landing reads in ${locale} and shows the waiting count`, async ({ page, context }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await useLocale(context, locale)
    await seal(context, { [COUNT_PATH]: { count: 7, enabled: true } })

    await page.goto('/sponsor')
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(say(locale, 'sponsorLanding.hero.heading'), { timeout: 60_000 })
    await expect(page.getByText(say(locale, 'sponsorLanding.hero.sub'))).toBeVisible()
    await expect(page.getByText(say(locale, 'sponsorLanding.hero.counter', { count: '7' }))).toBeVisible()

    // The page's own calls to action (the closing band repeats the hero's; both go to sign-up). Scoped
    // to <main>: the shared header's "Become a sponsor" nav link points at /sponsor itself.
    const ctas = page.locator('main').getByRole('link', { name: say(locale, 'sponsorLanding.hero.becomeSponsor') })
    for (const href of await ctas.evaluateAll((as) => as.map((a) => a.getAttribute('href')))) {
      expect(href).toBe('/sponsor/register')
    }
    const cta = ctas.first()
    await cta.click()
    await expect(page).toHaveURL(/\/sponsor\/register$/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(say(locale, 'sponsorAuth.registerTitle'), { timeout: 60_000 })

    expect(errors).toEqual([])
  })
}

test('the counter is hidden when nobody is waiting', async ({ page, context }) => {
  await seal(context, { [COUNT_PATH]: { count: 0, enabled: true } })
  await page.goto('/sponsor')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(say('en', 'sponsorLanding.hero.heading'), { timeout: 60_000 })
  const counterTail = say('en', 'sponsorLanding.hero.counter', { count: '' }).trim()
  await expect(page.getByText(counterTail)).toHaveCount(0)
})
