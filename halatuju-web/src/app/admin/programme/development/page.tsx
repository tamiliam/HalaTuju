'use client'

import { lazySource } from '@/components/source/LazySource'
import { useProgrammeScope } from '@/lib/programmeScopeCore'

/**
 * Programme → **Development** (student maintenance S10, 2026-11-02; the ModulesAdmin board): short modules that help
 * an organisation's funded scholars grow, done on My Bursary → Growth.
 *
 * ⚠ THE SCREEN IS ITS OWN CHUNK (`lazySource`, the house pattern): the route carries only this loader, so the
 * shared first-load median does not move. The chosen gift travels as `?programme=`; the server reads the
 * ORGANISATION from it (inside the caller's own) and refuses every role but super / org_admin / admin.
 */
const DevelopmentAdmin = lazySource(() => import('@/components/development/screens').then((m) => m.DevelopmentAdmin))

export default function DevelopmentPage() {
  // The chosen gift, read from the light context leaf (`programmeScopeCore`), not the provider module (S9 lesson).
  const programme = useProgrammeScope().chosen || undefined
  return <DevelopmentAdmin programme={programme} />
}
