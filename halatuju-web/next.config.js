const path = require('path')

/** NEXT_PUBLIC_ names the app reads that a build may leave unset — defined as '' then (TD-470, see `webpack`). */
const EMPTY_WHEN_UNSET = ['NEXT_PUBLIC_ORG_CODE', 'NEXT_PUBLIC_TURNSTILE_SITE_KEY', 'NEXT_PUBLIC_APP_VERSION']

/*
 * SEC-12 (TD-520, A1.9b): security headers on every web response, a CONSERVATIVE set that restricts
 * no load the site makes (the API, Supabase auth and storage, Turnstile's frame, the document viewer's
 * frame and the contract previews' `srcDoc` frames are all unaffected):
 *   - X-Content-Type-Options: nosniff — no MIME sniffing;
 *   - Referrer-Policy: strict-origin-when-cross-origin — the browsers' default, now stated; other
 *     sites see only our origin, never a path or a query string;
 *   - X-Frame-Options: SAMEORIGIN + CSP `frame-ancestors 'self'` — no other site may frame our pages
 *     (clickjacking); the only CSP directive set, and it restricts framing only, no loading;
 *   - Permissions-Policy — camera, microphone, geolocation, payment and USB off for the page and every
 *     frame in it; nothing here uses them (a document photo goes through a file input, which is not
 *     governed by it). Clipboard and fullscreen are left alone (the referral-link copy uses the clipboard).
 * No HSTS here (the API sends it; the web host's is the owner's call) and no loading CSP (a full one
 * would need Report-Only first). `securityHeaders.test.ts` pins the set.
 */
const SECURITY_HEADERS = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
  { key: 'Content-Security-Policy', value: "frame-ancestors 'self'" },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=(), usb=()' },
]

/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [{ source: '/:path*', headers: SECURITY_HEADERS }]
  },

  // Enable React strict mode
  reactStrictMode: true,

  // Standalone output for Docker/Cloud Run
  output: 'standalone',

  // Off since the 14.2.35 security patch and kept off on Next 15 (A1.1): there is no sharp in the
  // standalone image, so turning it on is TD-321's job (A2.5), not the upgrade's.
  images: { unoptimized: true },

  // Environment variables exposed to browser
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    // Per-org branding delivery (Sprint 6, D1). Unset or 'brightpath' ⇒ platform mode: the app
    // renders baked platform defaults and NEVER fetches (zero flash for BrightPath). Deliberately
    // unset on Cloud Run.
    // ⚠ '' HERE DEFINES NOTHING: Next skips a falsy `env` value. EMPTY_WHEN_UNSET below covers it.
    NEXT_PUBLIC_ORG_CODE: process.env.NEXT_PUBLIC_ORG_CODE || '',
  },

  /*
   * The design sandbox is COMPILED OUT of a normal build, not hidden at runtime.
   *
   * Next only treats a file as a route if its extension is in this list. The sandbox's pages are
   * named `page.sandbox.tsx`, so with the default extensions they are ordinary modules that no
   * route points at — the route does not exist, and neither the fixtures nor the stubbed fetch
   * reach a production bundle. A runtime `notFound()` would still ship both to every visitor.
   *
   * Set NEXT_PUBLIC_SANDBOX=1 to build the sandbox service. Unset is the default, and
   * `sandbox-safety.test.ts` asserts that default so nobody can flip it by accident.
   */
  pageExtensions: process.env.NEXT_PUBLIC_SANDBOX
    ? ['tsx', 'ts', 'jsx', 'js', 'sandbox.tsx']
    : ['tsx', 'ts', 'jsx', 'js'],

  /*
   * TD-360: `import x from '@/messages/en.json?slice=admin'` gets only that slice of the file,
   * cut at build time by `scripts/messages-slice-loader.js` (see its header). The message files
   * themselves are never changed or copied. `codeStandards.test.ts` asserts this rule exists and
   * points at the loader — a loader nobody wires is the TD-281 failure.
   */
  webpack(config, options) {
    config.module.rules.push({
      test: /[\\/]messages[\\/](en|ms|ta)\.json$/,
      resourceQuery: /slice=/,
      use: [{ loader: path.join(__dirname, 'scripts', 'messages-slice-loader.js') }],
    })
    /*
     * TD-470 (2026-11-03): a NEXT_PUBLIC_ name the build has NO value for stays a live
     * `process.env.X` read, and webpack then ships its `process` polyfill (~0.8 kB gz) — copied
     * into 73 chunks, on 89 of 102 routes and the root layout. Next will not inline '' (it skips
     * falsy `env` values), so each name the app may leave empty is defined as '' here when unset.
     * `NEXT_PUBLIC_ORG_CODE` is unset on Cloud Run on purpose, so production paid this too; the
     * Turnstile key and the version are set only by the Dockerfile, so the deploy gate's budget
     * build (the repo's .env files) paid it on top. '' and unset read alike: every reader tests
     * truthiness (`branding-context.tsx`, `turnstile.ts`, `appVersion.ts`). A SET value is left to
     * Next, so the two never define the same key. `publicEnv.test.ts` fails on a client read of a
     * NEXT_PUBLIC_ name nothing defines.
     */
    const unset = EMPTY_WHEN_UNSET.filter((name) => !process.env[name])
    if (unset.length && options && options.webpack) {
      config.plugins = config.plugins || []
      config.plugins.push(new options.webpack.DefinePlugin(
        Object.fromEntries(unset.map((name) => [`process.env.${name}`, JSON.stringify('')]))))
    }
    return config
  },
}

module.exports = nextConfig
