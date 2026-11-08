'use client'

// The Overview's per-person pending cards (T5c P5b, owner 2026-11-05). Drawn inside `ProgrammesLanding`'s chunk.
//
// ⚠ ONLY THE KEYS THE SERVER SENT ARE DRAWN: a card the caller may not see is ABSENT, never a zero.
// ⚠ A SERVED ZERO STAYS, MUTED (no sublines under any number, owner 2026-11-05); when EVERY card is zero one calm line says so above them.
// Visibility only: each card is a link to a page that checks the caller again.

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { getMyPending, type PendingCard, type PendingKey } from '@/lib/admin-api/myPending'

type Tone = 'caution' | 'critical'

/** Where each card opens, its label, and (for the reviewer's two) its tone. `small`: the quieter second row. */
const META: Record<PendingKey, { href: string; label: string; small?: boolean; tone?: Tone }> = {
  unassigned: { href: '/admin/scholarship?status=profile_complete&assigned=none&ready=1', label: 'admin.overview.unassigned' },
  overdue: { href: '/admin/scholarship?band=overdue', label: 'admin.overview.overdue' },
  awaiting_qc: { href: '/admin/scholarship?status=interviewed', label: 'admin.overview.awaitingQc' },
  sponsors_to_vet: { href: '/admin/sponsors', label: 'admin.overview.sponsorsToVet' },
  invitations: { href: '/admin/organisation/staff', label: 'admin.overview.invitations', small: true },
  payment_runs: { href: '/admin/payments', label: 'admin.overview.paymentRuns', small: true },
  requests: { href: '/admin/requests?tab=action', label: 'admin.overview.requests', small: true },
  // No page of its own for wallet credits: sponsors are where a credit is recorded and confirmed.
  wallet_credits: { href: '/admin/sponsors', label: 'admin.overview.walletCredits' },
  qc_awaiting: { href: '/admin/programme/overview', label: 'admin.overview.qcAwaiting' },
  // A1.13b: the Applications list narrowed to cases with a pending withdrawal request (`?withdrawal=pending`).
  award_withdrawals: { href: '/admin/scholarship?withdrawal=pending', label: 'admin.overview.awardWithdrawals' },
  my_open: { href: '/admin/scholarship?assigned=me&band=open', label: 'admin.overview.myOpen' },
  my_due_soon: { href: '/admin/scholarship?assigned=me&band=due_soon', label: 'admin.overview.myDueSoon', tone: 'caution' },
  my_overdue: { href: '/admin/scholarship?assigned=me&band=overdue', label: 'admin.overview.myOverdue', tone: 'critical' },
  mentees: { href: '/admin/my-students', label: 'admin.overview.mentees' },
  not_met: { href: '/admin/my-students', label: 'admin.overview.notMet' },
  asked_help: { href: '/admin/my-students', label: 'admin.overview.askedHelp' },
}

export default function PendingCards({ token }: { token: string | null }) {
  const { t } = useT()
  const [cards, setCards] = useState<PendingCard[] | null>(null)

  useEffect(() => {
    if (!token) return
    let live = true
    getMyPending({ token })
      .then((d) => { if (live) setCards(d.cards) })
      .catch(() => { if (live) setCards([]) })   // a failed strip is silence, not an error over the programmes
    return () => { live = false }
  }, [token])

  const shown = (cards ?? []).filter((c) => META[c.key])
  if (shown.length === 0) return null
  const allClear = shown.every((c) => c.count === 0)
  const main = shown.filter((c) => !META[c.key].small)
  const small = shown.filter((c) => META[c.key].small)
  // Nobody with only quiet cards (a finance login's runs and invitations) is left with a shrunken page.
  const rows: [PendingCard[], boolean][] = main.length ? [[main, false], [small, true]] : [[small, false]]

  return (
    <div data-testid="pending-cards" className="mt-4">
      {allClear && <p data-testid="pending-all-clear" className="text-sm text-ground-600">{t('admin.overview.allClear')}</p>}
      {rows.filter(([r]) => r.length > 0).map(([row, quiet], n) => (
        <ul key={n} className={`mt-3 grid divide-y divide-ground-100 rounded-xl border border-ground-200 bg-ground-0
          sm:divide-y-0 sm:gap-3 sm:border-0 sm:bg-transparent ${quiet ? 'sm:grid-cols-3' : 'sm:grid-cols-2 lg:grid-cols-4'}`}>
          {row.map((c) => <PendingTile key={c.key} card={c} />)}
        </ul>
      ))}
    </div>
  )
}

function PendingTile({ card }: { card: PendingCard }) {
  const { t } = useT()
  const m = META[card.key]
  const zero = card.count === 0
  const numTone = zero ? 'text-ground-400'
    : m.tone === 'critical' ? 'text-critical-600' : m.tone === 'caution' ? 'text-caution-700' : 'text-ground-900'
  return (
    <li>
      <Link href={m.href} data-testid={`pending-${card.key}`} data-zero={zero ? 'true' : 'false'}
        className={`flex min-h-11 items-center justify-between gap-3 px-4 py-3 transition-colors
          sm:block sm:rounded-xl sm:border sm:border-ground-200 sm:bg-ground-0 sm:p-4 sm:shadow-sm sm:hover:border-primary-300
          ${zero ? 'opacity-70' : ''}`}>
        <span className="text-xs font-semibold uppercase tracking-wider text-ground-500">{t(m.label)}</span>
        <span className="text-right sm:mt-1 sm:block sm:text-left">
          <span data-testid={`pending-count-${card.key}`} className={`text-2xl font-semibold tabular-nums ${numTone}`}>{card.count}</span>
        </span>
      </Link>
    </li>
  )
}
