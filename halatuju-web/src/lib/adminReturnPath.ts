/**
 * The admin sign-in's RETURN PATH (request #86, review round 1, 27 Nov 2026): a signed-out reviewer
 * who follows the "returned by QC" email's case link is sent to `/admin/login?next=<that page>` and,
 * once signed in, lands on that page rather than their role home.
 *
 * The hops, all on the canonical origin: the admin layout's guard writes `?next=` (`adminLoginHref`);
 * the password sign-in reads it (`nextFromSearch`); the Google button keeps it in this tab's
 * sessionStorage (`rememberAdminNext`) because the OAuth round trip comes back to the fixed
 * `/admin/auth/callback` URL, whose query Supabase owns — so the redirect allow-list is untouched —
 * and the callback takes it back (`takeRememberedAdminNext`). Every reader validates again.
 *
 * ⚠ AN OPEN REDIRECT IS THE RISK. `safeAdminNext` accepts only a same-origin path under `/admin/`:
 * the value is decoded ONCE (by `URLSearchParams`, in `nextFromSearch`) and then must start with
 * `/admin/`, and holds no backslash, no `//`, no whitespace or control character, no `%` at all (so
 * nothing still encoded, e.g. `%2F%2F`, can decode later into something else), no `.`/`..` segment,
 * and must resolve to the same origin. Anything else is refused and the caller falls back to
 * `adminLanding(role)`.
 */
import { adminLanding, mustCompleteProfile, type AdminRoleLike } from '@/lib/adminLanding'

const LOGIN = '/admin/login'
const STORE_KEY = 'halatuju_admin_next'
const BASE = 'https://return-path.invalid'

/** `value` when it is a safe same-origin `/admin/` path (already decoded once), else null. */
export function safeAdminNext(value: string | null | undefined): string | null {
  if (typeof value !== 'string' || value.length === 0 || value.length > 2048) return null
  if (!value.startsWith('/admin/')) return null
  if (/[\\%\s\u0000-\u001f\u007f]/.test(value) || value.includes('//')) return null
  const path = value.split(/[?#]/, 1)[0]
  if (path.split('/').some((seg) => seg === '.' || seg === '..')) return null
  // The sign-in pages themselves are never a destination (a loop, not a page).
  if (path === LOGIN || path.startsWith('/admin/auth/')) return null
  let url: URL
  try { url = new URL(value, BASE) } catch { return null }
  if (url.origin !== BASE || !url.pathname.startsWith('/admin/')) return null
  return value
}

/** The `next` of a query string (`window.location.search`), decoded once and validated. */
export function nextFromSearch(search: string): string | null {
  try { return safeAdminNext(new URLSearchParams(search).get('next')) } catch { return null }
}

/** The login URL for a signed-out visit to ``path`` (pathname + search): `?next=` only when safe. */
export function adminLoginHref(path: string): string {
  const next = safeAdminNext(path)
  return next ? `${LOGIN}?next=${encodeURIComponent(next)}` : LOGIN
}

/** Where a signed-in admin goes: the safe `next`, unless the first-login profile hold
 *  (`mustCompleteProfile`, the layout's own rule) would bounce them from it, else their role home. */
export function adminReturnTarget(role: AdminRoleLike, next: string | null | undefined): string {
  const safe = safeAdminNext(next)
  return safe && !mustCompleteProfile(role, safe) ? safe : adminLanding(role)
}

function store(): Storage | null {
  try { return typeof window === 'undefined' ? null : window.sessionStorage } catch { return null }
}

/** Keep a safe `next` across the Google OAuth round trip (this tab only); a null clears it. */
export function rememberAdminNext(next: string | null): void {
  const s = store()
  try {
    const safe = safeAdminNext(next)
    if (safe) s?.setItem(STORE_KEY, safe)
    else s?.removeItem(STORE_KEY)
  } catch { /* storage refused: the landing is the fallback */ }
}

/** The remembered `next`, validated again, and cleared so it is used once. */
export function takeRememberedAdminNext(): string | null {
  const s = store()
  try {
    const value = s?.getItem(STORE_KEY) ?? null
    s?.removeItem(STORE_KEY)
    return safeAdminNext(value)
  } catch { return null }
}
