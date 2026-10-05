import { notFound } from 'next/navigation'

/**
 * EVERY UNMATCHED `/sponsor/...` ADDRESS, SENT TO THE PORTAL'S OWN 404.
 *
 * ⚠ **IT EXISTS BECAUSE `app/sponsor/not-found.tsx` WAS UNREACHABLE WITHOUT IT.** That file
 * shipped with request #25 and nothing could render it: a nested `not-found.tsx` answers a
 * `notFound()` thrown inside its own subtree, and NOTHING under `/sponsor` throws one, so an
 * unmatched sponsor address fell all the way to the ROOT `app/not-found.tsx` — whose way out is
 * the PUBLIC site, which is the exact thing request #25 set out to stop. The console got its
 * catch-all in that sprint and the portal did not; this is the missing half, and it was found by
 * curling the live site after the deploy rather than by any test, because an inert page is green
 * in every suite.
 *
 * ⚠ **IT SHADOWS NOTHING, BY THE ROUTER'S OWN PRECEDENCE**: a static segment beats a dynamic one
 * and a dynamic one beats a catch-all, so `/sponsor` itself, `/sponsor/login`, `/sponsor/register`,
 * `/sponsor/pool/[id]`, `/sponsor/auth/...` and every `(portal)` route — `/sponsor/account`,
 * `/sponsor/students/[id]`, `/sponsor/my-students/[id]`, `/sponsor/terms`, `/sponsor/trust` — are
 * matched before this is considered. A route group's parentheses are not a URL segment, so the
 * `(portal)` routes live at `/sponsor/...` and win here exactly as the others do. That is a rule
 * of the router and not a thing to take on trust: the route table printed by `next build` is read
 * after this is added, and `src/app/sponsor/[...notFound]/page.test.tsx` pins that this is the
 * ONLY catch-all under `/sponsor`.
 *
 * ⚠⚠ **IT COSTS THE SAME HTTP STATUS THE CONSOLE'S DID: `/sponsor/<nonsense>` NOW ANSWERS 200
 * WHERE IT ANSWERED 404.** In Next 14.2 only the ROOT `not-found.tsx` sets the response status; a
 * NESTED boundary handling `notFound()` renders the right page and leaves the status at 200. That
 * was measured on this tree on 2026-10-05 with throwaway probe routes — see
 * `app/admin/[...notFound]/page.tsx`, which carries the full note, and docs/decisions.md. The
 * trade is taken knowingly and for the same reason: these addresses sit behind the portal, and a
 * sponsor who mistypes one gets a way back into the portal instead of being pushed onto the
 * public site. ⚠ RE-TEST ON A NEXT UPGRADE, alongside the console's.
 *
 * ⚠ Deliberately NOT `'use client'`: the throw belongs on the server, so no portal JS has to load
 * to decide the address is wrong. The page it lands on IS a client component, which is fine — the
 * boundary does not have to agree with the thrower.
 */
export default function SponsorCatchAll(): never {
  notFound()
}
