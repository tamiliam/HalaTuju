'use client'

import { useParams } from 'next/navigation'
import { lazySource } from '@/components/source/LazySource'

/**
 * Team → **a reviewer** (request #10; one person page since Sprint T3, 2026-11-09). The page itself is
 * `components/admin/person/TeamPersonPage`, the same for every team member, fetched as its own chunk
 * (`'ad'`, with the permission editor) so this route's entry carries one loader line.
 *
 * ⚠ The list route's guard (`mayOpen('/admin/organisation/reviewers')`) is applied inside; the endpoint
 * is the fence. ⚠ `ReviewerProfile` also holds a HOME ADDRESS: it is in no payload and never shown.
 */
const TeamPersonPage = lazySource(() =>
  import(/* webpackChunkName: 'ad' */ '@/components/admin/person/TeamPersonPage').then((m) => m.default))

export default function AdminReviewerDetailPage() {
  const params = useParams<{ id: string }>()
  return <TeamPersonPage entry="reviewer" id={Number(params?.id)} backTable="reviewers" />
}
