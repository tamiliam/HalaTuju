'use client'

import { useParams, useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { mayReadMentors } from '@/lib/pageGuard'
import { lazySource } from '@/components/source/LazySource'

/**
 * Team → Mentors → **a mentor** (Team tables T3, 2026-11-03; owner ruling 6): their work and how it is going.
 *
 * ⚠ THE ROUTE SITS UNDER `/admin/organisation/reviewers` ON PURPOSE, like `admins/[id]`: `canAccess`
 * resolves a path by its longest registered prefix, so the page belongs to the Team row (highlight, ⌘K)
 * without a registry row of its own; `mentors` is a static segment, so Next prefers it over `[id]`.
 * ⚠ WHO SEES IT is narrower than the Team row: exactly who reads the Mentors table (`mayReadMentors`, the
 * server's `mentor_invite.may_read`). `GET admin/mentors/<id>/` is the fence (403, and 404 for another
 * organisation's mentor). The screen is the Mentors table's own chunk (`MentorsAdmin`), loaded here by
 * its literal specifier — no new chunk.
 */
const MentorDetail = lazySource(() => import('@/components/mentors/MentorsAdmin').then((m) => m.MentorDetail))

export default function MentorDetailPage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  const params = useParams<{ id: string }>()
  const id = Number(params?.id)
  const router = useRouter()
  if (role && !mayReadMentors(role)) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  return <MentorDetail id={id} onDeleted={() => router.push('/admin/organisation/reviewers?tab=mentors')} />
}
