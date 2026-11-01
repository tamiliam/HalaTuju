'use client'

import { lazySource } from '@/components/source/LazySource'
import InvitationEmailsCard from '@/components/admin/InvitationEmailsCard'

/**
 * Organisation → **Mentors** (student maintenance S7a, 2026-10-31; the MentorsAdmin board).
 *
 * ⚠ THE SCREEN IS ITS OWN CHUNK. The route carries only this loader (`lazySource`, the house
 * pattern), so the page adds next to nothing to its first load — the shared first-load median has
 * a fraction of a kB of room (TD-427), and a new route lands IN that median.
 */
const MentorsAdmin = lazySource(() => import('@/components/mentors/MentorsAdmin').then((m) => m.default))

/**
 * ⚠ THE EMAILS TAB'S CARD IS IMPORTED HERE, BY THE ROUTE, AND HANDED IN (S7b follow-up review fix 5).
 * It needs the shared template editor; reached from the lazy screen, that editor's chunk became an
 * entry in the webpack runtime every route downloads. From the route it is ordinary first-load JS of
 * this admin page only (well under the median), and the screen itself stays lazy.
 */
export default function MentorsPage() {
  return <MentorsAdmin EmailsCard={InvitationEmailsCard} />
}
