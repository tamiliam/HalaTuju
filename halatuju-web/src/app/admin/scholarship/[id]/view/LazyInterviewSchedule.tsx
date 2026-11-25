'use client'

/**
 * The interview scheduling card, fetched as its own chunk only for a case that shows it.
 *
 * WHY (first-load budget, 2026-11-25): the 21:00 batch put `/admin/scholarship/[id]` at 250.107 kB
 * against its 250 kB ceiling, and the web build refused it. The card is drawn only when scheduling is
 * on, the case is assigned, and the case is `profile_complete` or `interviewing`; most visits never
 * draw it, yet it rode in every one. The budget is never raised; the weight is paid for here.
 *
 * The page keeps the card's condition unchanged and mounts this in its place. The import is owned by
 * `lazySource`, with a LITERAL specifier.
 */
import { lazySource } from '@/components/source/LazySource'

export const LazyInterviewScheduleCard = lazySource(
  () => import('@/components/admin/InterviewScheduleCard').then((m) => m.default),
)
