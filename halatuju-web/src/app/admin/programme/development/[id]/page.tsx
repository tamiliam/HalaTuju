'use client'

import { useParams } from 'next/navigation'
import { lazySource } from '@/components/source/LazySource'
import { useProgrammeScope } from '@/lib/programmeScopeCore'

/**
 * One module's **Progress** (student maintenance S10; the ModuleProgress board): per scholar, lessons read, the
 * task, the mentor, "Late", the review, the reminder and the CSV. Staff only — the server's fence (another
 * organisation's module is 404).
 *
 * ⚠ ITS OWN CHUNK (`lazySource`), like the Development list: the route carries only this loader.
 */
const ModuleProgressView = lazySource(() => import('@/components/development/screens').then((m) => m.ModuleProgressView))

export default function ModuleProgressPage() {
  const params = useParams()
  // The chosen gift, read from the light context leaf (`programmeScopeCore`), not the provider module (S9 lesson).
  const programme = useProgrammeScope().chosen || undefined
  return <ModuleProgressView id={Number(params?.id)} programme={programme} />
}
