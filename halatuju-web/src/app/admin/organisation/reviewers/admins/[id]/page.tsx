'use client'

import { useParams, useSearchParams } from 'next/navigation'
import { lazySource } from '@/components/source/LazySource'

/**
 * Team → **an admin-side team member** (Admin, Finance, an organisation admin; one person page since
 * Sprint T3, 2026-11-09): `components/admin/person/TeamPersonPage`, its own chunk (`'ad'`).
 *
 * ⚠ THE ROUTE SITS UNDER `/admin/organisation/reviewers` ON PURPOSE. `canAccess` resolves a path by its
 * longest registered prefix, so this page belongs to the Team row (same roles, same highlight, same ⌘K
 * entry) without a registry row of its own. `admins` is a static segment, so Next prefers it over the
 * reviewer page's `[id]`.
 * ⚠ THE GET IS THE FENCE, and it is narrower than the Team page: only a super or an organisation admin
 * may read anybody's permissions, an org_admin only their own organisation's team (404 otherwise).
 * `?table=admins|reviewers` (T2's links) picks the Team tab Back returns to.
 */
const TeamPersonPage = lazySource(() =>
  import(/* webpackChunkName: 'ad' */ '@/components/admin/person/TeamPersonPage').then((m) => m.default))

export default function AdminPersonPage() {
  const params = useParams<{ id: string }>()
  const asked = useSearchParams()?.get('table')
  return <TeamPersonPage entry="admin" id={Number(params?.id)} backTable={asked === 'reviewers' ? 'reviewers' : 'admins'} />
}
