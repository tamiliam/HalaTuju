'use client'

import { lazySource } from '@/components/source/LazySource'
import { useProgrammeParam } from '@/lib/programmeScope'

/**
 * Programme → **Announcements** (student maintenance S8, 2026-11-01; the AnnouncementsAdmin board): an
 * organisation's news to its funded scholars, read on My Bursary → News and optionally emailed.
 *
 * ⚠ THE SCREEN IS ITS OWN CHUNK (`lazySource`, the house pattern): the route carries only this loader, so
 * the shared first-load median does not move. The chosen gift travels as `?programme=`; the server reads
 * the ORGANISATION from it (inside the caller's own) and refuses every role but super / org_admin / admin.
 */
const AnnouncementsAdmin = lazySource(() => import('@/components/announcements/AnnouncementsAdmin').then((m) => m.default))

export default function AnnouncementsPage() {
  const programme = useProgrammeParam()
  return <AnnouncementsAdmin programme={programme} />
}
