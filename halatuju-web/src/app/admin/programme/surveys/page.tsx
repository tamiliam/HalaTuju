'use client'

import { lazySource } from '@/components/source/LazySource'
import { useProgrammeScope } from '@/lib/programmeScopeCore'

/**
 * Programme → **Surveys** (student maintenance S9, 2026-11-02; the SurveysAdmin board): an organisation's
 * questions to its funded scholars, answered on My Bursary → Surveys.
 *
 * ⚠ THE SCREEN IS ITS OWN CHUNK (`lazySource`, the house pattern): the route carries only this loader, so
 * the shared first-load median does not move. The chosen gift travels as `?programme=`; the server reads
 * the ORGANISATION from it (inside the caller's own) and refuses every role but super / org_admin / admin.
 */
const SurveysAdmin = lazySource(() => import('@/components/surveys/screens').then((m) => m.SurveysAdmin))

export default function SurveysPage() {
  // The chosen gift, read from the light context leaf (`programmeScopeCore`), not the provider module: with
  // `programmeScope` on this page webpack regrouped shared chunks and every student route grew ~1 kB (S9).
  const programme = useProgrammeScope().chosen || undefined
  return <SurveysAdmin programme={programme} />
}
