'use client'

/**
 * The pre-interview reject screens, fetched as their own chunk only for a case that can show them.
 *
 * WHY (first-load budget, 2026-11-23): F3 made `PreInterviewReject.tsx` heavier (the four-fact
 * assessment now sits in the form) and `/admin/scholarship/[id]` went to 250.9 kB against its
 * 250 kB ceiling. Most cases never draw either screen, yet both rode in every visit. The budget is
 * never raised; the weight is paid for here.
 *
 * The record is mounted under the SAME condition as the component's own early return: the case is
 * `rejected` in the pre-interview category. Keep that condition identical. The import is owned by `lazySource`, with LITERAL specifiers.
 *
 * The OPTION's element is passed to the cockpit on every case (the card decides whether to show it);
 * the component itself returns null without `app.pre_interview`. So it uses the
 * QUIET fallback (nothing while loading): a "Loading..." line would sit under the assign controls on
 * every case with no option. It stays mounted (keyed by case) because it holds its pending reply
 * across a reload.
 */
import { lazySource } from '@/components/source/LazySource'

export const LazyPreInterviewOption = lazySource(
  () => import('./PreInterviewReject').then((m) => m.PreInterviewOption),
  { quiet: true },
)

export const LazyPreInterviewRecord = lazySource(
  () => import('./PreInterviewReject').then((m) => m.PreInterviewRecord),
)
