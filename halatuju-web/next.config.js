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
}

module.exports = nextConfig
