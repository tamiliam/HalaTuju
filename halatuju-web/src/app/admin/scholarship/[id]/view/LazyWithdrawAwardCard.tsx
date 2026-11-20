'use client'

/**
 * The withdraw-award card, fetched as its own chunk only for a case that carries a withdraw request.
 *
 * WHY (LL sprint close, 2026-11-19): `/admin/scholarship/[id]` read 250.595 kB first-load against a
 * 250 kB ceiling. The card (~300 lines) draws nothing unless the case has a `withdrawal_request`
 * with a status or a step for this user, yet it rode in every visit. The budget is never raised; the
 * weight is paid for here. The cockpit mounts this wrapper under the SAME condition as the card's own
 * early return (`withdrawal_request` with a `status` or a `your_step`), so it never hides a card that
 * would draw; the card keeps its early return. Keep the two conditions identical.
 *
 * The import is owned by `lazySource` (a failed chunk says so in place; `next/dynamic` would throw),
 * with a LITERAL specifier so the bundler emits a real chunk.
 */
import { lazySource } from '@/components/source/LazySource'

export const LazyWithdrawAwardCard = lazySource(
  () => import('./WithdrawAwardCard').then((m) => m.WithdrawAwardCard),
)
