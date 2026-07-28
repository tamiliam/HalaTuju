// One active PRIVILEGED scope per identity — except super admins.
//
// The partner console (sees student PII) and the sponsor portal (anonymised pool) are
// two privileged scopes that can be reached by the SAME Google identity. We deliberately
// allow only ONE of them to be active at a time per browser: signing into one ends the
// other's local session. SUPER ADMINS are exempt (they may hold both). This is an
// intentional policy — not Supabase's emergent behaviour — so it's predictable + testable.
//
// Mechanism: the three Supabase clients use separate storageKeys, so ending one scope's
// session (`signOut({ scope: 'local' })`) leaves the others untouched; the change in
// localStorage propagates to any other tab on that scope via the client's storage listener.
import { getAdminSupabase } from './admin-supabase'
import { getSponsorSupabase } from './sponsor-supabase'
import { effectiveRole } from './navigation'

type Scope = 'admin' | 'sponsor'

/**
 * Is this path inside one of the privileged consoles (the partner console or the sponsor
 * portal), which run their own isolated auth?
 *
 * The boundary matters and is not decoration: a bare `startsWith('/admin')` also swallows
 * `/administrivia`, so a future student route could silently inherit console behaviour. Same
 * class of bug as the route registry's `/admin` prefix (fixed in nav/IA N1) — a prefix rule
 * needs an exception for anything that is not actually a section.
 */
export function isPrivilegedConsolePath(pathname: string | null | undefined): boolean {
  if (!pathname) return false
  return ['/admin', '/sponsor'].some((p) => pathname === p || pathname.startsWith(p + '/'))
}

/**
 * Should the student auth stack stay inert on this path?
 *
 * TWO REASONS, ONE EFFECT — and they are kept separate on purpose. A privileged console is inert
 * because it runs its own isolated auth (above). The design SANDBOX is inert because it must not
 * touch real auth infrastructure at all: it is handed to people outside the organisation, and
 * `AuthProvider` otherwise mints an anonymous Supabase user on mount — a real auth row created by
 * a design review.
 *
 * ⚠ Do NOT collapse this by adding '/sandbox' to `isPrivilegedConsolePath`. The sandbox is not a
 * privileged console, that predicate is read as a security statement elsewhere, and quietly
 * widening its meaning is how a display rule becomes mistaken for a boundary — the 2026-07-15
 * surface-partition incident in miniature.
 */
export function isAnonymousAuthSuppressed(pathname: string | null | undefined): boolean {
  if (!pathname) return false
  if (isPrivilegedConsolePath(pathname)) return true
  return pathname === '/sandbox' || pathname.startsWith('/sandbox/')
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
// Set on the scope that was ended, read by that scope's login page to explain why.
const SUPERSEDED_KEY = 'halatuju_scope_superseded'

async function isSuperIdentity(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/admin/role/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    })
    const data = await res.json()
    return effectiveRole(data) === 'super'
  } catch {
    return false  // fail-closed: treat as non-super (enforce the policy)
  }
}

function setItem(k: string, v: string) { try { localStorage.setItem(k, v) } catch { /* ignore */ } }
function getItem(k: string): string | null { try { return localStorage.getItem(k) } catch { return null } }
function delItem(k: string) { try { localStorage.removeItem(k) } catch { /* ignore */ } }

/**
 * Call right after a successful sign-in to `current`. Ends the OTHER privileged scope's
 * local session for this browser (super admins keep both). `isSuper` may be passed when
 * already known (the admin paths have it); otherwise it's resolved from `token`.
 */
export async function enforceSingleScope(
  current: Scope,
  opts: { token: string; isSuper?: boolean },
): Promise<void> {
  // A fresh sign-in to `current` clears any stale "you were superseded here" marker.
  if (getItem(SUPERSEDED_KEY) === current) delItem(SUPERSEDED_KEY)

  const isSuper = opts.isSuper ?? await isSuperIdentity(opts.token)
  if (isSuper) return

  const other: Scope = current === 'admin' ? 'sponsor' : 'admin'
  const client = current === 'admin' ? getSponsorSupabase() : getAdminSupabase()
  const { data: { session } } = await client.auth.getSession()
  if (!session) return  // nothing else active — no message needed

  await client.auth.signOut({ scope: 'local' })
  setItem(SUPERSEDED_KEY, other)
}

/** Peek (no clear) — lets a layout decide to route a freshly-superseded tab to its login. */
export function wasScopeSuperseded(scope: Scope): boolean {
  return getItem(SUPERSEDED_KEY) === scope
}

/** Read + clear — the login page calls this once to show the "signed out elsewhere" note. */
export function consumeSuperseded(scope: Scope): boolean {
  if (wasScopeSuperseded(scope)) { delItem(SUPERSEDED_KEY); return true }
  return false
}
