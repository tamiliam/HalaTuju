/**
 * SEC-12 (TD-520, A1.9b): the web's security headers, set in `next.config.js` `headers()`.
 *
 * A conservative set that restricts NO load the site makes: no loading CSP (only `frame-ancestors`),
 * and the Permissions-Policy turns off only features nothing here uses. A change that widens it into
 * a loading policy, or drops a header, fails here first. The live check after a deploy:
 *   curl -sI https://halatuju.xyz/ | grep -iE "x-content-type|referrer-policy|x-frame|content-security|permissions-policy"
 */
// eslint-disable-next-line @typescript-eslint/no-require-imports
const nextConfig = require('../../../next.config.js')

type Header = { key: string; value: string }

async function headerMap(): Promise<{ source: string; map: Record<string, string> }> {
  const rules = await nextConfig.headers()
  expect(rules).toHaveLength(1)
  const map: Record<string, string> = {}
  for (const h of rules[0].headers as Header[]) map[h.key] = h.value
  return { source: rules[0].source, map }
}

it('applies to every path', async () => {
  expect((await headerMap()).source).toBe('/:path*')
})

it('sets exactly the five headers, with these values', async () => {
  expect((await headerMap()).map).toEqual({
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'X-Frame-Options': 'SAMEORIGIN',
    'Content-Security-Policy': "frame-ancestors 'self'",
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
  })
})

it('the CSP restricts framing only, never a load (Supabase, Turnstile, the API, images)', async () => {
  const csp = (await headerMap()).map['Content-Security-Policy']
  const directives = csp.split(';').map((d) => d.trim().split(/\s+/)[0]).filter(Boolean)
  expect(directives).toEqual(['frame-ancestors'])
})

it('leaves the clipboard and fullscreen alone (the referral-link copy uses the clipboard)', async () => {
  const pp = (await headerMap()).map['Permissions-Policy']
  expect(pp).not.toMatch(/clipboard|fullscreen/)
})
