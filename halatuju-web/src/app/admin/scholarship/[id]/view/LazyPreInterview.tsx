'use client'

/**
 * The pre-interview reject screens, fetched as their own chunk only for a case that can show them.
 *
 * WHY (first-load budget, 2026-11-23): F3 made `PreInterviewReject.tsx` heavier (the four-fact
 * assessment now sits in the form) and `/admin/scholarship/[id]` went to 250.9 kB against its
 * 250 kB ceiling. Most cases never draw either screen, yet both rode in every visit. The budget is
 * never raised; the weight is paid for here.
 *
 * The cockpit mounts each wrapper under the SAME condition as the component's own early return:
 *   - option: `app.pre_interview` is set (the component returns null without it; `AssignAndWitness`
 *     already mounts the slot only when it is set);
 *   - record: the case is `rejected` in the pre-interview category.
 * Keep the conditions identical. The import is owned by `lazySource`, with LITERAL specifiers.
 */
import { lazySource } from '@/components/source/LazySource'

export const LazyPreInterviewOption = lazySource(
  () => import('./PreInterviewReject').then((m) => m.PreInterviewOption),
)

export const LazyPreInterviewRecord = lazySource(
  () => import('./PreInterviewReject').then((m) => m.PreInterviewRecord),
)
