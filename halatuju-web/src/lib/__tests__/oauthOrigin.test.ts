import {
  CANONICAL_LOOPBACK_HOST,
  canonicalLoopbackUrl,
  isLoopbackAlias,
  oauthOriginMismatchAtEntry,
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

describe('oauthOriginMismatchAtEntry', () => {
  it('is true when a code arrives at an origin holding no verifier — the TD-182 failure', () => {
    expect(oauthOriginMismatchAtEntry('?code=abc', ADMIN, storageWith({}))).toBe(true)
  })

  it('is false when this origin holds the verifier — the flow can proceed', () => {
    expect(oauthOriginMismatchAtEntry('?code=abc', ADMIN, storageWith({
      'halatuju_admin_session-code-verifier': 'v',
    }))).toBe(false)
  })

  it('is false with no code — that is a different failure and wants a different sentence', () => {
    expect(oauthOriginMismatchAtEntry('', ADMIN, storageWith({}))).toBe(false)
    expect(oauthOriginMismatchAtEntry('?error=access_denied', ADMIN, storageWith({}))).toBe(false)
  })

  it('reads the key for the scope it was asked about, not a sibling scope', () => {
    // The sponsor verifier being present says nothing about the admin flow: separate clients,
    // separate storage keys. Confusing them would blame the wrong cause on a real failure.
    expect(oauthOriginMismatchAtEntry('?code=abc', ADMIN, storageWith({
      'halatuju_sponsor_session-code-verifier': 'v',
    }))).toBe(true)
  })

  it('claims nothing when there is no storage to inspect', () => {
    // SSR, or a browser with storage blocked. An unreadable vault is not evidence of an empty one.
    expect(oauthOriginMismatchAtEntry('?code=abc', ADMIN, null)).toBe(false)
  })

  /**
   * The regression that gives this function its `AtEntry` name.
   *
   * First shipped, it was called AFTER `getSession()`. `detectSessionInUrl` runs an exchange
   * during client init and `_exchangeCodeForSession` deletes the verifier once it has POSTed —
   * success or failure alike (auth-js 2.95.3, GoTrueClient.js:788). So by the time the question
   * was asked, a consumed verifier and an absent one looked identical, and every unrelated
   * exchange failure was reported to the person as "you started somewhere else". The owner hit
   * it within the hour of deploy, on the very host the sign-in HAD started from.
   *
   * The function itself was never wrong — the call site was. These two cases pin the meaning so
   * the distinction survives, and the page reads the answer before constructing the client.
   */
  describe('the reading is only meaningful before an exchange can run', () => {
    it('a consumed verifier is INDISTINGUISHABLE from one that was never here', () => {
      const beforeExchange = storageWith({ 'halatuju_admin_session-code-verifier': 'v' })
      const afterExchange = storageWith({})  // supabase removed it, whatever the outcome

      expect(oauthOriginMismatchAtEntry('?code=abc', ADMIN, beforeExchange)).toBe(false)
      expect(oauthOriginMismatchAtEntry('?code=abc', ADMIN, afterExchange)).toBe(true)
    })

    it('so a caller must snapshot the answer, not re-ask for it', () => {
      // What the pages now do: read once at entry, carry the boolean, use it only to EXPLAIN a
      // failure that has actually happened. Re-reading here would flip a correct false to true.
      const storage = storageWith({ 'halatuju_admin_session-code-verifier': 'v' })
      const snapshot = oauthOriginMismatchAtEntry('?code=abc', ADMIN, storage)
      expect(snapshot).toBe(false)
      expect(oauthOriginMismatchAtEntry('?code=abc', ADMIN, storageWith({}))).not.toBe(snapshot)
    })
  })
})
