'use client'

import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { adminLanding } from '@/lib/adminLanding'
import { useT } from '@/lib/i18n'

/**
 * THE CONSOLE'S OWN 404 — the one an admin sees, inside the console they are signed in to.
 *
 * ⚠ **WHY A SECOND 404 PAGE AT ALL.** The root `app/not-found.tsx` sends you to `/` — the PUBLIC
 * site. A signed-in officer who mistyped a console address was dumped out of the console
 * altogether, and the giveaway that this was wrong rather than a sign-out is that pressing Back
 * twice put them straight back to work: the session had never ended. This file renders inside
 * `app/admin/layout.tsx`, which mounts `AdminAuthProvider`, so it can read who is here and offer
 * them their own way back — with the menu and the shell still around it.
 *
 * ⚠ **THE DESTINATION IS DERIVED, NEVER NAMED.** `adminLanding(role)` → `defaultRoute()` →
 * the route registry in `lib/navigation.ts`. docs/decisions.md 2026-09-08 ("Where an admin lands
 * is DERIVED from the registry, not named") and docs/lessons.md both record what a hard-coded
 * landing cost: four roles bounced off their own page, and `finance` sent somewhere it can only
 * ever be refused. A literal `/admin` here would reintroduce exactly that, silently, for the
 * roles that cannot see it.
 *
 * ⚠ `role` is null only while the role call is in flight, and the layout holds its own loading
 * state in front of us until it resolves — so `?? {}` is a belt, not the normal path. It reads
 * as the least-privileged role rather than as the most, which is the safe direction to be wrong.
 *
 * ⚠ A nested `not-found.tsx` in Next 14 catches `notFound()` thrown inside its own subtree — it
 * does NOT catch an address that matched no route (that one goes to the ROOT page). The
 * `[...notFound]` catch-all beside it is what turns a mistyped console address into a throw this
 * page can answer; delete one and the other stops meaning anything.
 */
export default function AdminNotFound() {
  const { role } = useAdminAuth()
  const { t } = useT()

  return (
    <div className="text-center mt-12" data-testid="admin-not-found">
      <p className="text-6xl font-bold text-primary-600 mb-2">404</p>
      <h1 className="text-xl font-semibold text-ground-900 mb-2">{t('errors.pageNotFound')}</h1>
      <p className="text-ground-500 text-sm mb-6">{t('errors.pageNotFoundDesc')}</p>
      <Link
        href={adminLanding(role ?? {})}
        className="inline-block px-5 py-2.5 bg-brand-fill hover:bg-brand-fill-hover text-brand-fill-ink text-sm font-medium rounded-lg transition-colors"
      >
        {t('errors.backToConsole')}
      </Link>
    </div>
  )
}
