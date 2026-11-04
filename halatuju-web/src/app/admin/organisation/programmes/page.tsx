'use client'

/**
 * Organisation → Programmes — the landing for everyone on the partner login (T5c P5, owner 2026-11-04).
 *
 * From 2026-09-03 this route was a redirect to Organisation → Overview, where the gift cards then lived. It is
 * a page again: the gift-door roles see the full card grid, everyone else the programmes where they have work
 * (`ProgrammesLanding.tsx`). The server is the fence (`my-programmes/` serves only the caller's programmes);
 * this page only declines to draw for a caller the menu would not show it to.
 *
 * ⚠ THE LANDING IS ITS OWN CHUNK (`lazySource`, a literal specifier). Imported statically it carried the gift
 * grid and its API into this route's first load (147 kB) and took the bundle-budget MEDIAN over its 145 kB
 * line; behind the boundary the route is the shell's weight and the cards arrive a moment later.
 */
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { mayOpen } from '@/lib/pageGuard'
import { lazySource } from '@/components/source/LazySource'

const ProgrammesLanding = lazySource(() => import('@/components/admin/ProgrammesLanding').then((m) => m.default))

export default function ProgrammesPage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  if (!role) return null
  if (!mayOpen('/admin/organisation/programmes', role)) {
    return <p className="text-critical-600">{t('admin.programmes.landing.noAccess')}</p>
  }
  return <ProgrammesLanding />
}
