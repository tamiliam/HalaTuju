'use client'

import { useParams } from 'next/navigation'
import { lazySource } from '@/components/source/LazySource'

/**
 * Team → Mentors → **a mentor** (Team tables T3, 2026-11-03; one person page since Sprint T3,
 * 2026-11-09): `components/admin/person/TeamPersonPage`, its own chunk (`'ad'`), which loads the
 * Mentors table's chunk (`MentorsAdmin`) for the mentor parts by its literal specifier — no new chunk.
 *
 * ⚠ THE ROUTE SITS UNDER `/admin/organisation/reviewers` ON PURPOSE, like `admins/[id]`; `mentors` is a
 * static segment, so Next prefers it over `[id]`.
 * ⚠ WHO SEES IT is narrower than the Team row: exactly who reads the Mentors table (`mayReadMentors`,
 * the server's `mentor_invite.may_read`). `GET admin/mentors/<id>/` is the fence (403, and 404 for
 * another organisation's mentor). The id is the MENTOR record's, not the sign-in's.
 */
const TeamPersonPage = lazySource(() =>
  import(/* webpackChunkName: 'ad' */ '@/components/admin/person/TeamPersonPage').then((m) => m.default))

export default function MentorDetailPage() {
  const params = useParams<{ id: string }>()
  return <TeamPersonPage entry="mentor" id={Number(params?.id)} backTable="mentors" />
}
