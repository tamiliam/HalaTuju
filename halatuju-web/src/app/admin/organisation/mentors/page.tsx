'use client'

import { lazySource } from '@/components/source/LazySource'

/**
 * Organisation → **Mentors** (student maintenance S7a, 2026-10-31; the MentorsAdmin board).
 *
 * ⚠ THE SCREEN IS ITS OWN CHUNK. The route carries only this loader (`lazySource`, the house
 * pattern), so the page adds next to nothing to its first load — the shared first-load median has
 * a fraction of a kB of room (TD-427), and a new route lands IN that median.
 */
const MentorsAdmin = lazySource(() => import('@/components/mentors/MentorsAdmin').then((m) => m.default))

export default function MentorsPage() {
  return <MentorsAdmin />
}
