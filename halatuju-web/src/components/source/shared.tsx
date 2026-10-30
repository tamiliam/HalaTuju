'use client'

import Link from 'next/link'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { contractStageKey, stageLabelKey, stageTone } from '@/lib/sourceConsole'
import type { SourceContract } from '@/lib/admin-api'

/**
 * The source console's shared pieces (source sign-in S3 + S4, 2026-10-30). Design of record: the
 * owner-approved mock-ups of 2026-10-30 (Overview, Applications, Student, Witness, Scholars,
 * Profile). Built from the console's own tokens — the mock's inline styles are not copied.
 *
 * ⚠ EVERY SOURCE COMPONENT CALLS `admin/source/…` ONLY (`lib/admin-api/sourceConsole`). A source
 * user is refused every staff endpoint, and `noStaffCalls.test.tsx` holds the pages to it.
 */

export type T = (k: string, vars?: Record<string, string>) => string
export const K = 'admin.sourceConsole'
export const CARD = 'rounded-xl border border-ground-200 bg-ground-0 p-5'

/** The source this user signs in for, from `/admin/role/` (S1's `source_name`). */
export function useSourceName(): string {
  const { role } = useAdminAuth()
  return role?.source_name ?? ''
}

/** Where a contract waiting for this source's witness is signed: the student's own page, opened
 *  on its witness step (`SourceStudent` reads `?step=witness` on arrival). A step, not a route of its
 *  own — a new route would have cost every visitor's median (`npm run bundle-budget`). */
export const witnessHref = (id: number) => `/admin/scholarship/${id}?step=witness`

export function StageBadge({ stage, t }: { stage: string; t: T }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${stageTone(stage)}`}>
      {t(stageLabelKey(stage))}
    </span>
  )
}

export function PageTitle({ title, subtitle, children }: {
  title: string; subtitle?: string; children?: React.ReactNode
}) {
  return (
    <div className="mb-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-ground-900">{title}</h1>
        {children}
      </div>
      {subtitle && <p className="mt-1 text-sm text-ground-500">{subtitle}</p>}
    </div>
  )
}

export function Footnote({ children }: { children: React.ReactNode }) {
  return <p className="mt-4 text-xs text-ground-500">{children}</p>
}

/** A card of label → value rows (Profile, Application). An empty value reads as a dash. */
export function FactsCard({ title, rows, testId }: {
  title: string; rows: Array<[string, React.ReactNode]>; testId?: string
}) {
  return (
    <section className={CARD} data-testid={testId}>
      <h2 className="mb-3 text-base font-semibold text-ground-900">{title}</h2>
      <dl className="grid grid-cols-[8.5rem_1fr] gap-x-3 gap-y-2 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-ground-500">{label}</dt>
            <dd className="min-w-0 break-words text-ground-900">{value || '—'}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

const PARTIES = [
  ['student', 'student_signed_at'], ['guarantor', 'guarantor_signed_at'],
  ['witness', 'witness_signed_at'], ['foundation', 'foundation_signed_at'],
] as const

/** The signing chain, one line a party: "Student — signed 24 Oct 2026". While this source's
 *  witness is awaited, the witness reads "waiting for you" and the Foundation "after the witness". */
export function ContractParties({ contract, t }: { contract: SourceContract; t: T }) {
  const value = (party: (typeof PARTIES)[number][0], at: string | null) => {
    if (at) return t(`${K}.contract.signedOn`, { date: formatDate(at) })
    if (party === 'witness' && contract.can_witness) return t(`${K}.contract.waitingYou`)
    if (party === 'foundation' && !contract.witness_signed_at && contract.can_witness) {
      return t(`${K}.contract.afterWitness`)
    }
    return t(`${K}.contract.notYet`)
  }
  return (
    <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2" data-testid="contract-parties">
      {PARTIES.map(([party, key]) => (
        <div key={party} className="flex gap-2">
          <dt className="text-ground-500">{t(`${K}.contract.party.${party}`)}:</dt>
          <dd className="font-medium text-ground-900">{value(party, contract[key])}</dd>
        </div>
      ))}
    </dl>
  )
}

/**
 * The contract on a student's page. Waiting for THIS source's witness (`can_witness`, the server's
 * one predicate) it is the amber call to act — "Review and witness"; once this source has
 * witnessed, it says so and keeps the way back to the document. Never a name or an amount: dates.
 */
export function SourceContractCard({ applicationId, contract, t, onWitness }: {
  applicationId: number; contract: SourceContract | null; t: T
  /** On the student's own page: open its witness step in place (a link to the same page would not
   *  re-mount it). Elsewhere (a scholar's page) the card links there. */
  onWitness?: () => void
}) {
  const toWitness = (label: string, cls: string) => (onWitness
    ? <button type="button" onClick={onWitness} className={cls}>{label}</button>
    : <Link href={witnessHref(applicationId)} className={cls}>{label}</Link>)
  if (!contract) {
    return (
      <section className={CARD} data-testid="source-contract">
        <h2 className="text-base font-semibold text-ground-900">{t(`${K}.contract.title`)}</h2>
        <p className="mt-2 text-sm text-ground-600">{t(`${K}.contract.none`)}</p>
      </section>
    )
  }
  if (contract.can_witness) {
    return (
      <section data-testid="source-contract"
        className="flex flex-col gap-3 rounded-xl border border-caution-200 bg-caution-50 p-5 sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-caution-900">{t(`${K}.contract.waiting`)}</h2>
          <div className="mt-2"><ContractParties contract={contract} t={t} /></div>
        </div>
        {toWitness(t(`${K}.contract.review`),
          'shrink-0 rounded-lg bg-brand-fill px-4 py-2.5 text-center text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover')}
      </section>
    )
  }
  const witnessed = contract.witness_is_you && contract.witness_signed_at
  return (
    <section className={CARD} data-testid="source-contract">
      <h2 className="text-base font-semibold text-ground-900">{t(`${K}.contract.title`)}</h2>
      <p className="mb-3 mt-1 text-sm text-ground-600">{t(contractStageKey(contract.status))}</p>
      <ContractParties contract={contract} t={t} />
      {witnessed && contract.witness_signed_at && (
        <p className="mt-3 text-sm text-positive-700">
          {t(`${K}.contract.youWitnessed`, { date: formatDate(contract.witness_signed_at) })}{' '}
          {toWitness(t(`${K}.contract.view`), 'font-medium text-primary-600 hover:underline')}
        </p>
      )}
    </section>
  )
}
