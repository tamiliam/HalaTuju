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

type Scope = 'admin' | 'sponsor'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
// Set on the scope that was ended, read by that scope's login page to explain why.
const SUPERSEDED_KEY = 'halatuju_scope_superseded'

async function isSuperIdentity(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/admin/role/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    })
    const data = await res.json()
    return !!(data?.is_super_admin || data?.role === 'super')
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
