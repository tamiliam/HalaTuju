'use client'

import { useParams } from 'next/navigation'
import { lazySource } from '@/components/source/LazySource'

/**
 * Team → **a person's mentor page** (Sprint M2a, owner U1/U2, 2026-11-11):
 * `components/admin/person/MentorGroupPage`, its own chunk (`'ad'`), which loads the Mentors table's chunk
 * (`MentorsAdmin`) for the mentor parts by its literal specifier — no new chunk.
 *
 * ⚠ THE ROUTE SITS UNDER `/admin/organisation/team` ON PURPOSE, like `admins/[id]`.
 * ⚠ WHO SEES IT is narrower than the Team row: exactly who reads the Mentors table (`mayReadMentors`,
 * the server's `mentor_invite.may_read`). `GET admin/mentors/<id>/` is the fence (403, and 404 for
 * another organisation's mentor). The id is the MENTOR record's, not the sign-in's.
 */
const MentorGroupPage = lazySource(() =>
  import(/* webpackChunkName: 'ad' */ '@/components/admin/person/MentorGroupPage').then((m) => m.default))

export default function MentorDetailPage() {
  const params = useParams<{ id: string }>()
  return <MentorGroupPage id={Number(params?.id)} />
}
