'use client'
// One scholar's maintenance file (student maintenance Sprint 2). Design of record: the owner-approved
// canvas, 2026-10-29 (file artboard).
//
// ⚠ A SHELL, HONESTLY: only what exists is shown. The header and the Overview's Results, Money and
// Contract cards read the server's payload; Mentor (Sprint 7), Letters (Sprint 6) and Surveys (later)
// say calmly that they are coming — never sample data. Real standing is Sprint 4, spending Sprint 5,
// the signed-PDF link Sprint 5.
// ⚠ THE SUB-STATE AND CLOSE LIVE HERE since Sprint 3 (`ScholarControls`, moved from the cockpit's
// PostAwardPanels): drawn from the server's `controls` offer, judged again by the cockpit doors. A
// hold is a money act (payments rights, S1 M1). "View application" opens the full review screen.
// ⚠ A record this admin may not read, another organisation's, or one with no file all come back
// 404 — `RecordState` says so neutrally (never "does not exist", never "no access").

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import PanelTabs, { type PanelTab } from '@/components/admin/PanelTabs'
import RecordState from '@/components/admin/RecordState'
import ScholarActivity from '@/components/admin/ScholarActivity'
import ScholarControls from '@/components/admin/ScholarControls'
import ScholarResults from '@/components/admin/ScholarResults'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { formatDate } from '@/lib/formatDate'
import { rm } from '@/lib/programmeOverview'
import { statusLabelKey, statusTone } from '@/lib/applicationStatus'
import { STANDING_TONE, SUBSTATE_TONE } from '@/lib/scholars'
import { getScholarFile, type ScholarFile } from '@/lib/admin-api'

type Tab = 'overview' | 'results' | 'money' | 'contract' | 'letters' | 'mentoring' | 'surveys' | 'activity'
const TABS: readonly PanelTab<Tab>[] = [
  { key: 'overview', labelKey: 'admin.scholars.tab.overview' },
  { key: 'results', labelKey: 'admin.scholars.tab.results' },
  { key: 'money', labelKey: 'admin.scholars.tab.money' },
  { key: 'contract', labelKey: 'admin.scholars.tab.contract' },
  { key: 'letters', labelKey: 'admin.scholars.tab.letters' },
  { key: 'mentoring', labelKey: 'admin.scholars.tab.mentoring' },
  { key: 'surveys', labelKey: 'admin.scholars.tab.surveys' },
  { key: 'activity', labelKey: 'admin.scholars.tab.activity' },
]

const CARD = 'rounded-xl border border-ground-200 bg-ground-0 p-5'
const money = (v: string | null | undefined) => (v == null ? '—' : `RM${rm(v)}`)

function Card({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) {
  return (
    <article className={`${CARD} flex flex-col gap-2`} data-testid={testId}>
      <h2 className="text-base font-semibold text-ground-900">{title}</h2>
      {children}
    </article>
  )
}

function Later({ text }: { text: string }) {
  return <p className="text-sm text-ground-500">{text}</p>
}

export default function ScholarFilePage() {
  const params = useParams()
  const id = Number(params?.id)
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = canAccess('/admin/scholars', effectiveRole(role), role?.permissions)
  const [file, setFile] = useState<ScholarFile | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('overview')
  // A control's change re-reads the file (sub-state, close and the activity log all move together).
  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    if (!token || !allowed || !Number.isFinite(id)) { setLoading(false); return }
    let live = true
    setLoading(true)
    getScholarFile(id, { token })
      .then((f) => { if (live) setFile(f) })
      .catch(() => { if (live) setFile(null) })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [id, token, allowed, reloads])

  if (role && !allowed) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  if (!file) return <RecordState loading={loading} />

  const result = file.latest_result
  // The money links: shown only to a viewer who may open each page, and carrying the file's gift so
  // the page opens on THIS student's gift rather than asking (or showing another's).
  const viewer = effectiveRole(role)
  const giftQuery = file.gift ? `?programme=${encodeURIComponent(file.gift.code)}` : ''
  const moneyLinks = (['payments', 'spending'] as const)
    .filter((page) => canAccess(`/admin/${page}`, viewer, role?.permissions))
  const fundedSince = file.vircle_activated_at || file.awarded_at
  const sub = [file.gift?.name, [file.course, file.institution].filter(Boolean).join(', '),
    t('admin.scholars.file.applicationNo', { id: String(file.id) })].filter(Boolean).join(' · ')

  const resultsCard = (
    <Card title={t('admin.scholars.card.results')} testId="card-results">
      {result ? (
        <>
          <p className="flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular-nums text-ground-900">{result.cgpa ?? '—'}</span>
            <span className="text-sm text-ground-600">
              {t('admin.scholars.file.cgpaFor', { semester: result.semester || '—' })}
            </span>
          </p>
          <p className="text-sm text-ground-600">
            {t('admin.scholars.file.recordedOn', { date: formatDate(result.at) })}
          </p>
        </>
      ) : <Later text={t('admin.scholars.file.noResult')} />}
      {file.next_due && (
        <p className="text-xs text-ground-600" data-testid="file-next-due">
          {t('admin.scholars.file.nextDue', { date: formatDate(file.next_due) })}
        </p>
      )}
      {file.thresholds && (
        <p className="text-xs text-ground-500">
          {t('admin.scholars.file.thresholds', { min: file.thresholds.minimum, failing: file.thresholds.failing })}
        </p>
      )}
      <button type="button" onClick={() => setTab('results')} className="self-start text-sm text-primary-600 hover:underline">
        {t('admin.scholars.file.openResults')}
      </button>
    </Card>
  )
  const moneyCard = (
    <Card title={t('admin.scholars.card.money')} testId="card-money">
      <div className="grid grid-cols-3 gap-2 text-sm">
        {(['award_amount', 'paid_to_date', 'remaining'] as const).map((k) => (
          <div key={k}>
            <div className="text-ground-600">{t(`admin.scholars.money.${k}`)}</div>
            <div className="text-base font-semibold tabular-nums text-ground-900">{money(file.money[k])}</div>
          </div>
        ))}
      </div>
      <p className="text-sm text-ground-700">
        {file.money.last_payment
          ? t('admin.scholars.money.lastPayment', {
            amount: money(file.money.last_payment.amount), date: formatDate(file.money.last_payment.at) })
          : t('admin.scholars.money.noPayment')}
      </p>
      {moneyLinks.length > 0 && (
        <p className="flex gap-4 text-sm">
          {moneyLinks.map((page) => (
            <Link key={page} href={`/admin/${page}${giftQuery}`} className="text-primary-600 hover:underline">
              {t(page === 'payments' ? 'admin.scholars.money.openPayments' : 'admin.scholars.money.openSpending')}
            </Link>
          ))}
        </p>
      )}
    </Card>
  )
  const contractCard = (
    <Card title={t('admin.scholars.card.contract')} testId="card-contract">
      <p className="text-sm text-ground-700">
        {file.contract.exists && file.contract.status
          ? t(`admin.scholars.contract.${file.contract.status}`)
          : t('admin.scholars.contract.none')}
      </p>
    </Card>
  )
  const later = (key: 'mentor' | 'letters' | 'surveys') => (
    <Card title={t(`admin.scholars.card.${key}`)} testId={`card-${key}`}>
      <Later text={t(`admin.scholars.later.${key}`)} />
    </Card>
  )

  return (
    <div>
      <Link href="/admin/scholars" className="text-sm text-primary-600 hover:underline">
        ← {t('admin.scholars.title')}
      </Link>

      <header className={`${CARD} my-4 flex flex-wrap items-start justify-between gap-4`}>
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-ground-900">{file.name || '—'}</h1>
          <p className="mt-1 text-sm text-ground-600">{sub}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusTone(file.status)}`}>
              {t(statusLabelKey(file.status))}
            </span>
            {file.status !== 'closed' && (
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${SUBSTATE_TONE[file.maintenance_substate]}`}
                data-testid="file-substate">
                {t(`admin.maintenance.substate.${file.maintenance_substate}`)}
              </span>
            )}
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STANDING_TONE[file.standing]}`}>
              {t(`admin.scholars.standing.${file.standing}`)}
            </span>
            {fundedSince && (
              <span className="rounded-full bg-ground-100 px-2.5 py-0.5 text-xs font-medium text-ground-700">
                {t('admin.scholars.file.fundedSince', { date: formatDate(fundedSince) })}
              </span>
            )}
          </div>
        </div>
        <Link href={`/admin/scholarship/${file.id}`}
          className="inline-flex h-10 items-center rounded-lg border border-ground-300 bg-ground-0 px-4 text-sm text-ground-700 hover:bg-ground-50">
          {t('admin.scholars.file.viewApplication')}
        </Link>
        <div className="basis-full">
          <ScholarControls key={`${file.status}-${file.maintenance_substate}`} file={file} token={token}
            onChanged={() => setReloads((n) => n + 1)} />
        </div>
      </header>

      <PanelTabs tabs={TABS} active={tab} onSelect={setTab} ariaLabelKey="admin.scholars.file.tabsLabel" />

      {tab === 'overview' && (
        <div className="flex flex-wrap items-start gap-5">
          <section aria-label={t('admin.scholars.file.summary')}
            className="grid min-w-0 flex-[999_1_560px] grid-cols-1 gap-4 md:grid-cols-2">
            {resultsCard}{moneyCard}{contractCard}{later('mentor')}{later('letters')}{later('surveys')}
          </section>
          <div className="min-w-0 flex-[1_1_320px] lg:max-w-md">
            <ScholarActivity key={reloads} id={file.id} token={token} compact readOnly={!file.in_maintenance} />
          </div>
        </div>
      )}
      {tab === 'results' && (
        <div className="max-w-3xl">
          <ScholarResults id={file.id} token={token} canReview={!!file.controls?.can_review_results}
            onChanged={() => setReloads((n) => n + 1)} />
        </div>
      )}
      {tab === 'money' && <div className="max-w-xl">{moneyCard}</div>}
      {tab === 'contract' && <div className="max-w-xl">{contractCard}</div>}
      {tab === 'letters' && <div className="max-w-xl">{later('letters')}</div>}
      {tab === 'mentoring' && <div className="max-w-xl">{later('mentor')}</div>}
      {tab === 'surveys' && <div className="max-w-xl">{later('surveys')}</div>}
      {tab === 'activity' && <div className="max-w-3xl"><ScholarActivity key={reloads} id={file.id} token={token} readOnly={!file.in_maintenance} /></div>}
    </div>
  )
}
