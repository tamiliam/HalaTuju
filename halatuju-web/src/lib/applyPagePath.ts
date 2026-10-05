/**
 * Where to send a student BACK to the apply form — naming the gift she was applying to.
 *
 * ⚠ A BARE `/scholarship/apply` NOW ASKS AFRESH (2026-10-05). It used to reuse whatever code an
 * earlier visit in the tab had stored, so a student who once followed Sabah's link and later came
 * back through the landing page was filed under Sabah without being asked. So the two legitimate
 * round trips — the My Results → onboarding detour and the sign-in gate (`/auth/callback` included)
 * — carry the code in the URL instead of relying on storage surviving a bare arrival.
 *
 * Its OWN leaf, not part of `./applyReturn`: the sign-in gate is mounted on every page and must not
 * pull `scholarship.ts` in, and `./applyReturn` rides (via `scholarship.ts`) on routes such as
 * `/profile` and `/scholarship/application` that never send anyone back to the form.
 */
import { APPLY_PROGRAMME_KEY, safeSession, type StorageLike } from './applyReturn'

export function applyPagePath(storage?: StorageLike): string {
  const s = storage ?? safeSession()
  const code = (s?.getItem(APPLY_PROGRAMME_KEY) ?? '').trim()
  return code ? `/scholarship/apply?p=${encodeURIComponent(code)}` : '/scholarship/apply'
}
