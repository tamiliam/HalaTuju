import { notFound } from 'next/navigation'

/**
 * EVERY UNMATCHED `/admin/...` ADDRESS, SENT TO THE CONSOLE'S OWN 404.
 *
 * ⚠ **IT EXISTS BECAUSE A NESTED `not-found.tsx` CANNOT CATCH AN UNMATCHED URL.** In the Next 14
 * app router, `app/admin/not-found.tsx` answers a `notFound()` thrown somewhere in its own
 * subtree; an address that matched NO route at all is answered by the ROOT `app/not-found.tsx`,
 * whose way out is the public site. This page is the one route that `/admin/<anything>` can still
 * match, and all it does is throw — so the nearest boundary, `app/admin/not-found.tsx`, renders
 * it, inside the admin layout and its `AdminAuthProvider`.
 *
 * ⚠ **IT SHADOWS NOTHING, BY THE ROUTER'S OWN PRECEDENCE**: a static segment beats a dynamic one
 * and a dynamic one beats a catch-all, so every real console route — `/admin/payments`,
 * `/admin/payments/[id]`, `/admin/sponsors/terms/[id]` — is matched before this is considered.
 * That is a rule of the router and not a thing to take on trust: the route table printed by
 * `next build` was read after this was added, and `src/lib/__tests__/navigation.test.ts` pins
 * that the catch-all is here and that it is the ONLY one under `/admin`.
 *
 * ⚠⚠ **WHAT IT COSTS, MEASURED AND NOT GUESSED: `/admin/<nonsense>` NOW ANSWERS HTTP 200 WHERE
 * IT USED TO ANSWER 404.** In Next 14.2 only the ROOT `not-found.tsx` sets the response status;
 * a NESTED boundary handling `notFound()` renders the right page and leaves the status at 200.
 * Proved on this tree on 2026-10-05 with two throwaway probe routes (a server-only layout chain
 * and a client one) built and served with `next start`: both answered 200, and `/nonsense` —
 * which reaches the root boundary — answered 404. So it is the router, not this file and not the
 * `'use client'` on `app/admin/layout.tsx`. The trade was taken deliberately: the person who
 * mistyped a console address gets the console's 404 and a way back into their own work, and the
 * addresses that lost the status sit behind the admin auth gate. See docs/decisions.md
 * 2026-10-05. ⚠ RE-TEST THIS ON A NEXT UPGRADE — if a later version sets the status on a nested
 * boundary, this note is what says the 200 was never wanted.
 *
 * ⚠ It is deliberately NOT `'use client'`: the throw belongs on the server so no console JS has
 * to load to decide the address is wrong. The page it lands on IS a client component, which is
 * fine — the boundary does not have to agree with the thrower.
 */
export default function AdminCatchAll(): never {
  notFound()
}
