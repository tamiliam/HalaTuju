/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React strict mode
  reactStrictMode: true,

  // Standalone output for Docker/Cloud Run
  output: 'standalone',

  // Environment variables exposed to browser
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    // Per-org branding delivery (Sprint 6, D1). Unset or 'brightpath' ⇒ platform mode: the app
    // renders baked platform defaults and NEVER fetches (zero flash for BrightPath). Deliberately
    // unset on Cloud Run.
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
}

module.exports = nextConfig
