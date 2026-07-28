import {
  CANONICAL_LOOPBACK_HOST,
  canonicalLoopbackUrl,
  isLoopbackAlias,
  oauthOriginMismatch,
  verifierKeyFor,
} from '../oauthOrigin'

/**
 * These tests encode the reproduction that closed TD-182 on 2026-07-28.
 *
 * Driven in a real browser: starting a Google sign-in at `http://localhost:3000/admin/login`
 * wrote `halatuju_admin_session-code-verifier` into localStorage, and it was still there at
 * `http://localhost:3000/admin/auth/callback`. Visiting the SAME callback path at
 * `http://127.0.0.1:3000` found localStorage completely empty and reproduced the owner's error
 * word for word. Same machine, same server, same browser — different origin, different vault.
 */

/** Minimal storage double — the helpers take a `getItem` and nothing more. */
const storageWith = (entries: Record<string, string>) => ({
  getItem: (k: string) => (k in entries ? entries[k] : null),
})

const ADMIN = 'halatuju_admin_session'

describe('verifierKeyFor', () => {
  it('matches the key supabase-js actually writes', () => {
    // auth-js 2.95.3 GoTrueClient.js: `${this.storageKey}-code-verifier`. If a supabase upgrade
    // ever renames this, the mismatch banner silently stops firing — so pin the convention.
    expect(verifierKeyFor(ADMIN)).toBe('halatuju_admin_session-code-verifier')
  })
})

describe('isLoopbackAlias', () => {
  it.each(['127.0.0.1', '[::1]', '::1'])('treats %s as a loopback alias', (host) => {
    expect(isLoopbackAlias(host)).toBe(true)
  })

  it('does not treat the canonical host as an alias — it is the destination', () => {
    expect(isLoopbackAlias(CANONICAL_LOOPBACK_HOST)).toBe(false)
  })

  it.each(['halatuju.xyz', 'halatuju-web-abc.a.run.app', '127.0.0.1.evil.com'])(
    'leaves %s alone',
    (host) => {
      expect(isLoopbackAlias(host)).toBe(false)
    },
  )
})

describe('canonicalLoopbackUrl', () => {
  it('rewrites the loopback IP to localhost, keeping port, path, query and hash', () => {
    expect(canonicalLoopbackUrl('http://127.0.0.1:3000/admin/login?next=%2Fadmin#x'))
      .toBe('http://localhost:3000/admin/login?next=%2Fadmin#x')
  })

  it('rewrites IPv6 loopback too', () => {
    expect(canonicalLoopbackUrl('http://[::1]:3000/sponsor/login'))
      .toBe('http://localhost:3000/sponsor/login')
  })

  it('returns null when already canonical, so a caller cannot loop', () => {
    expect(canonicalLoopbackUrl('http://localhost:3000/admin/login')).toBeNull()
  })

  it('is inert in production — this guard must never move a live sign-in', () => {
    expect(canonicalLoopbackUrl('https://halatuju.xyz/admin/login')).toBeNull()
    expect(canonicalLoopbackUrl('https://halatuju-web-x.a.run.app/admin/login')).toBeNull()
  })

  it('does not fall for a hostname that merely CONTAINS the loopback IP', () => {
    // `127.0.0.1.evil.com` resolves wherever its owner likes; rewriting it to localhost would
    // be a redirect we invented rather than one the person asked for.
    expect(canonicalLoopbackUrl('http://127.0.0.1.evil.com/admin/login')).toBeNull()
  })

  it('returns null for something that is not a URL at all', () => {
    expect(canonicalLoopbackUrl('not a url')).toBeNull()
  })
})

describe('oauthOriginMismatch', () => {
  it('is true when a code arrives at an origin holding no verifier — the TD-182 failure', () => {
    expect(oauthOriginMismatch('?code=abc', ADMIN, storageWith({}))).toBe(true)
  })

  it('is false when this origin holds the verifier — the flow can proceed', () => {
    expect(oauthOriginMismatch('?code=abc', ADMIN, storageWith({
      'halatuju_admin_session-code-verifier': 'v',
    }))).toBe(false)
  })

  it('is false with no code — that is a different failure and wants a different sentence', () => {
    expect(oauthOriginMismatch('', ADMIN, storageWith({}))).toBe(false)
    expect(oauthOriginMismatch('?error=access_denied', ADMIN, storageWith({}))).toBe(false)
  })

  it('reads the key for the scope it was asked about, not a sibling scope', () => {
    // The sponsor verifier being present says nothing about the admin flow: separate clients,
    // separate storage keys. Confusing them would blame the wrong cause on a real failure.
    expect(oauthOriginMismatch('?code=abc', ADMIN, storageWith({
      'halatuju_sponsor_session-code-verifier': 'v',
    }))).toBe(true)
  })

  it('claims nothing when there is no storage to inspect', () => {
    // SSR, or a browser with storage blocked. An unreadable vault is not evidence of an empty one.
    expect(oauthOriginMismatch('?code=abc', ADMIN, null)).toBe(false)
  })
})
