/**
 * The Overview's pending cards (T5c P5b, 2026-11-05): what is waiting on THIS caller, one read.
 *
 * ⚠ A LEAF, NOT IN THE `admin-api` BARREL (same reason as `myProgrammes.ts`): only `ProgrammesLanding`, its own
 * lazy chunk, imports this.
 * ⚠ A CARD THE CALLER MAY NOT SEE IS ABSENT. Render only the keys served; never invent a zero for a missing one.
 */
import { adminFetch } from './client'
import type { ApiOptions } from './client'

export type PendingKey =
  | 'unassigned' | 'overdue' | 'awaiting_qc' | 'sponsors_to_vet'
  | 'invitations' | 'payment_runs' | 'requests'
  | 'wallet_credits' | 'qc_awaiting'
  | 'award_withdrawals'   // A1.13b: withdrawal requests waiting for THIS checker's decision
  | 'my_open' | 'my_due_soon' | 'my_overdue'
  | 'mentees' | 'not_met' | 'asked_help'

export interface PendingCard {
  key: PendingKey
  count: number
  due_soon?: number
  oldest_days?: number
}

export async function getMyPending(options?: ApiOptions) {
  return adminFetch<{ cards: PendingCard[] }>('/api/v1/admin/scholarship/my-pending/', options)
}
