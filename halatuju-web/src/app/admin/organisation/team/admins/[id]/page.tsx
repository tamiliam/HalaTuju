'use client'

import { useParams } from 'next/navigation'
import { lazySource } from '@/components/source/LazySource'

/**
 * Team → **a person's admin page** (Sprint M2a, owner U1/U2, 2026-11-11): admin work only —
 * `components/admin/person/AdminGroupPage`, its own chunk (`'ad'`, with the permission editor), so this
 * route's entry carries one loader line.
 *
 * ⚠ THE ROUTE SITS UNDER `/admin/organisation/team` ON PURPOSE. `canAccess` resolves a path by its longest
 * registered prefix, so this page belongs to the Team row (same roles, same highlight, same ⌘K entry)
 * without a registry row of its own. `admins` is a static segment, beside `reviewers` and `mentors`.
 * ⚠ THE GET IS THE FENCE, and it is narrower than the Team page: only a super or an organisation admin
 * may read anybody's permissions, an org_admin only their own organisation's team (404 otherwise).
 * The old `reviewers/admins/<id>` address redirects here (`next.config.js`); its `?table=` is no longer
 * read — somebody who is not an admin is sent on to their own page (`lib/teamPaths.wrongGroupTarget`).
 */
const AdminGroupPage = lazySource(() =>
  import(/* webpackChunkName: 'ad' */ '@/components/admin/person/AdminGroupPage').then((m) => m.default))

export default function AdminPersonPage() {
  const params = useParams<{ id: string }>()
  return <AdminGroupPage id={Number(params?.id)} />
}
