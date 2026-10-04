/**
 * The version the Settings page shows — the BUILD's, never a typed number (TD-076, 2026-10-05).
 *
 * It was `const VERSION = '2.26.1'`, bumped by hand at release, and it had already gone stale once
 * (`2.0.0` for months). Now the deploy stamps it: `cloudbuild.yaml` passes `$COMMIT_SHA` into the
 * image build (`--build-arg COMMIT_SHA`), the Dockerfile sets `NEXT_PUBLIC_APP_VERSION` from it,
 * and Next inlines that at build time. So the page names the exact commit that is serving, and it
 * cannot drift. A local or test build has no SHA and says `dev`.
 *
 * ⚠ Read as the literal `process.env.NEXT_PUBLIC_APP_VERSION`: Next only inlines a NEXT_PUBLIC_
 * variable it can see spelled out. Shortened to seven characters, git's own short form.
 */
export function appVersion(): string {
  const sha = (process.env.NEXT_PUBLIC_APP_VERSION || '').trim()
  return sha ? sha.slice(0, 7) : 'dev'
}
