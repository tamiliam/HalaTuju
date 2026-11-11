'use client'

import { useParams } from 'next/navigation'
import { lazySource } from '@/components/source/LazySource'

/**
 * Team → **a person's reviewer page** (request #10; one page per group since Sprint M2a, owner U1/U2):
 * `components/admin/person/ReviewerGroupPage`, fetched as its own chunk (`'ad'`, with the permission
 * editor) so this route's entry carries one loader line. The old `reviewers/<id>` address redirects here.
 *
 * ⚠ The list route's guard (`mayOpen('/admin/organisation/team')`) is applied inside; the endpoint is the
 * fence. ⚠ `ReviewerProfile` also holds a HOME ADDRESS: it is in no payload and never shown.
 */
const ReviewerGroupPage = lazySource(() =>
  import(/* webpackChunkName: 'ad' */ '@/components/admin/person/ReviewerGroupPage').then((m) => m.default))

export default function AdminReviewerDetailPage() {
  const params = useParams<{ id: string }>()
  return <ReviewerGroupPage id={Number(params?.id)} />
}
