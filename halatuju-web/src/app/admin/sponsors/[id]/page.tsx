'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { effectiveRole } from '@/lib/navigation'
import {
  canRecordCredit, canSetMembership, creditActions, creditableProgrammes, creditChain,
  creditErrorKey, hasNoMoney, membershipErrorKey, membershipRows, pendingTotal, seenBand,
  studentStage,
} from '@/lib/sponsorDetail'
import {
  getSponsorDetail, recordSponsorCredit, setSponsorMembership, signSponsorCredit,
  voidSponsorCredit,
  type AdminSponsorDetail,
} from '@/lib/admin-api'
import { PAGE_SIZE_OPTIONS } from '@/lib/tableView'
import { usePagedRows, type PagedRows } from '@/lib/usePagedRows'
import { Pagination } from '@/components/Pagination'

// One sponsor, whole — the page that did not exist until 2026-07-27. Money first, because
// that is the question you open a sponsor to answer; then what it is funding, then who they
// brought with them.
//
// The ACCOUNT is platform-level and shown in full; the MONEY and the STUDENTS are fenced to
// the caller's organisation server-side. `detail.fenced` tells us to say so rather than let
// an org admin read a partial figure as the sponsor's whole giving record.

const money = (v: string) => Number(v).toLocaleString('en-MY', { minimumFractionDigits: 2 })

const statusBadge = (s: string) =>
  s === 'approved' ? 'bg-positive-100 text-positive-700'
    : s === 'pending' ? 'bg-caution-100 text-caution-700'
      : s === 'suspended' ? 'bg-caution-fill text-caution-fill-ink'
        : 'bg-critical-100 text-critical-600'

const creditBadge = (s: string) =>
  s === 'confirmed' ? 'bg-positive-100 text-positive-700'
    : s === 'cancelled' ? 'bg-ground-100 text-ground-500'
      : 'bg-caution-100 text-caution-700'

function Block({ title, action, children, note }: {
  title: string
  action?: React.ReactNode
  children: React.ReactNode
  note?: string
}) {
  return (
    <section className="bg-ground-0 rounded-xl shadow-sm border overflow-hidden">
      <div className="flex items-center justify-between gap-4 flex-wrap px-4 sm:px-5 py-3.5 border-b">
        <h2 className="text-[11.5px] font-semibold uppercase tracking-wider text-ground-600">{title}</h2>
        {action}
      </div>
      {children}
      {note && <p className="px-4 sm:px-5 py-3 text-xs text-ground-500 max-w-3xl">{note}</p>}
    </section>
  )
}

const inputCls = 'border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-info-200'

/**
 * The paging footer for one of the detail tables.
 *
 * Renders NOTHING below the threshold — the `Pagination` component itself would still draw its
 * page-size selector on a single page, and a footer on a table of one credit is furniture. On
 * production today only the sponsorship history (38 rows for one sponsor) reaches it.
 */
function TableFooter({ paged }: { paged: PagedRows<unknown> }) {
  if (!paged.visible) return null
  return (
    <div className="px-4 sm:px-5 pb-4">
      <Pagination
        page={paged.page} totalPages={paged.totalPages} pageSize={paged.pageSize}
        onPageChange={paged.setPage}
        pageSizeOptions={PAGE_SIZE_OPTIONS} onPageSizeChange={paged.setPageSize}
      />
    </div>
  )
}

export default function AdminSponsorDetailPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const params = useParams<{ id: string }>()
  const id = Number(params?.id)
  const viewerRole = effectiveRole(role)

  const [detail, setDetail] = useState<AdminSponsorDetail | null>(null)
  const [error, setError] = useState('')
  // One busy flag and one error line for the whole credits block: only one action can be in
  // flight at a time, and a second Sign fired mid-request would race the reload.
  const [busy, setBusy] = useState(false)
  const [creditError, setCreditError] = useState('')
  const [recording, setRecording] = useState(false)
  const [form, setForm] = useState({ programme_id: '', amount: '', external_reference: '' })
  // The accept / take-back panel gets its OWN busy flag and error line. It sits in a separate
  // block from the credits, and sharing one would have a refused acceptance print its message
  // above the money.
  const [giftBusy, setGiftBusy] = useState(0)
  const [giftError, setGiftError] = useState('')
  // Typed name per credit — the signature is per row, so one shared input would let a click
  // on row B submit the name typed for row A.
  const [typedNames, setTypedNames] = useState<Record<number, string>>({})

  const load = useCallback(() => {
    if (!token || !id) return Promise.resolve()
    return getSponsorDetail(id, { token })
      .then(setDetail)
      .catch(() => setError(t('admin.sponsors.detail.loadFailed')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  useEffect(() => { load() }, [load])

  /**
   * Run one credit mutation, then RE-FETCH the whole record.
   *
   * The response carries the updated credit, but confirming one moves the wallet tiles, the
   * pending caveat and `available` too — patching the row locally would leave the money on
   * screen disagreeing with the money in the database, which is the one thing this page
   * exists to stop.
   */
  const runCreditAction = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setCreditError('')
    try {
      await fn()
      await load()
      return true
    } catch (e) {
      const code = (e as { code?: string }).code
      setCreditError(t(`admin.sponsors.detail.creditError.${creditErrorKey(code)}`))
      return false
    } finally {
      setBusy(false)
    }
  }

  // These three sit ABOVE the early returns on purpose: hooks cannot be called conditionally, so
  // they read through `detail?.` and simply page an empty list until the record arrives.
  const pagedCredits = usePagedRows(detail?.credits ?? [])
  const pagedStudents = usePagedRows(detail?.sponsorships ?? [])
  const pagedReferrals = usePagedRows(detail?.referrals ?? [])

  if (error) return <div className="text-critical-600">{error}</div>
  if (!detail) return <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>

  const pending = pendingTotal(detail.credits)
  const creditable = creditableProgrammes(detail)
  const mayRecord = canRecordCredit(viewerRole) && creditable.length > 0
  const gifts = membershipRows(detail)
  const maySetGift = canSetMembership(viewerRole)

  /**
   * Accept into a gift, or take it back — then RE-FETCH the whole record.
   *
   * Same reasoning as `runCreditAction`: an acceptance changes what may be credited, so a
   * local row patch would leave the credit form offering a gift the database disagrees about.
   */
  const setGift = async (programmeId: number, next: 'approved' | 'rejected') => {
    setGiftBusy(programmeId)
    setGiftError('')
    try {
      await setSponsorMembership(detail.id, { programme_id: programmeId, status: next },
        { token: token! })
      await load()
    } catch (e) {
      const code = (e as { code?: string }).code
      setGiftError(t(`admin.sponsors.detail.giftError.${membershipErrorKey(code)}`))
    } finally {
      setGiftBusy(0)
    }
  }

  const submitRecord = async () => {
    const programmeId = Number(form.programme_id || creditable[0]?.programme_id)
    if (!programmeId) return
    const ok = await runCreditAction(() => recordSponsorCredit({
      sponsor_id: detail.id,
      programme_id: programmeId,
      amount: form.amount.trim(),
      external_reference: form.external_reference.trim(),
    }, { token: token! }))
    if (ok) {
      setRecording(false)
      setForm({ programme_id: '', amount: '', external_reference: '' })
    }
  }

  return (
    <div className="max-w-5xl font-plex flex flex-col gap-5">
      <Link href="/admin/sponsors" className="text-xs text-ground-500 hover:text-info-600">
        ← {t('admin.sponsors.title')}
      </Link>

      {/* ── who they are ─────────────────────────────────────────────────────── */}
      <section className="bg-ground-0 rounded-xl shadow-sm border px-4 sm:px-5 py-4 flex flex-col gap-2.5">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-bold text-ground-900">{detail.name || '—'}</h1>
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusBadge(detail.status)}`}>
            {detail.status}
          </span>
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-ground-100 text-ground-600">
            {t(`admin.sponsors.detail.digest.${detail.notify_frequency}`)}
          </span>
          {detail.is_trusted && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-ground-100 text-ground-600">
              {t('admin.sponsors.detail.trusted')}
            </span>
          )}
        </div>
        <div className="text-sm text-ground-600 flex flex-wrap gap-x-4 gap-y-1">
          <span>{detail.email || '—'}</span>
          {detail.phone && <span>{detail.phone}</span>}
          {detail.organisation && <span>{detail.organisation}</span>}
        </div>
        <div className="text-[13px] text-ground-500 flex flex-wrap gap-x-4 gap-y-1">
          <span>{t('admin.sponsors.detail.registeredOn', { date: formatDate(detail.created_at) })}</span>
          {detail.reviewed_by && (
            <span>{t('admin.sponsors.detail.vettedBy', {
              who: detail.reviewed_by,
              date: detail.reviewed_at ? formatDate(detail.reviewed_at) : '—',
            })}</span>
          )}
          <span
            className={seenBand(detail.last_seen_at) === 'never' || seenBand(detail.last_seen_at) === 'dormant'
              ? 'text-caution-700 font-medium' : ''}
            title={detail.last_seen_at ? undefined : t('admin.sponsors.seen.neverHint')}
          >
            {detail.last_seen_at
              ? t(`admin.sponsors.seen.${seenBand(detail.last_seen_at)}`, { date: formatDate(detail.last_seen_at) })
              : t('admin.sponsors.seen.never')}
          </span>
          {detail.consent_version && (
            <span>{t('admin.sponsors.detail.consent', { version: detail.consent_version })}</span>
          )}
        </div>
        {detail.note && <p className="text-sm text-ground-600 whitespace-pre-wrap">{detail.note}</p>}
      </section>

      {/* ── the money, one wallet per gift programme ─────────────────────────── */}
      {detail.fenced && (
        <p className="text-xs text-ground-500">{t('admin.sponsors.detail.fencedNote')}</p>
      )}

      {hasNoMoney(detail) ? (
        <Block title={t('admin.sponsors.detail.walletTitle')}>
          <p className="px-4 sm:px-5 py-5 text-sm text-ground-500">
            {t('admin.sponsors.detail.noWallet')}
          </p>
        </Block>
      ) : detail.programmes.map((w) => (
        <Block key={w.programme_id ?? 'none'} title={w.programme_name || t('admin.sponsors.detail.noProgramme')}>
          <div className="grid gap-3 sm:grid-cols-3 px-4 sm:px-5 py-4">
            {([
              ['given', w.given, t('admin.sponsors.detail.creditsCount', { count: String(w.credits) })],
              ['committed', w.committed, t('admin.sponsors.detail.studentsCount', { count: String(w.students) })],
              ['available', w.available, ''],
            ] as const).map(([key, value, sub]) => (
              <div key={key} className={`rounded-lg border p-3.5 ${key === 'available' ? 'bg-info-50 border-transparent' : 'bg-ground-50'}`}>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-ground-500">
                  {t(`admin.sponsors.detail.${key}`)}
                </div>
                <div className={`text-2xl font-bold tabular-nums ${key === 'available' ? 'text-info-700' : 'text-ground-900'}`}>
                  RM {money(value)}
                </div>
                {sub && <div className="text-xs text-ground-500 mt-0.5">{sub}</div>}
              </div>
            ))}
          </div>
        </Block>
      ))}

      {pending > 0 && (
        <p className="flex items-baseline gap-2.5 rounded-lg bg-caution-50 border border-caution-200 px-4 py-2.5 text-sm text-caution-700">
          <span aria-hidden>◆</span>
          <span>{t('admin.sponsors.detail.pendingCaveat', { amount: money(String(pending)) })}</span>
        </p>
      )}

      {/* ── wallet credits + their sign-off chain ────────────────────────────── */}
      <Block
        title={t('admin.sponsors.detail.creditsTitle')}
        note={t('admin.sponsors.detail.creditsNote')}
        action={mayRecord && !recording ? (
          <button
            onClick={() => { setRecording(true); setCreditError('') }}
            className="rounded-lg bg-brand-fill px-3 py-1.5 text-xs font-semibold text-brand-fill-ink hover:bg-brand-fill-hover"
          >
            + {t('admin.sponsors.detail.recordCredit')}
          </button>
        ) : undefined}
      >
        {creditError && (
          <div className="mx-4 sm:mx-5 mt-3 rounded-lg border border-critical-200 bg-critical-50 px-3 py-2 text-sm text-critical-600">
            {creditError}
          </div>
        )}

        {recording && mayRecord && (
          <div className="mx-4 sm:mx-5 mt-3 rounded-lg border bg-ground-50 p-3.5">
            <p className="text-sm font-semibold text-ground-900">{t('admin.sponsors.detail.recordCredit')}</p>
            <p className="mt-1 text-xs text-ground-500 max-w-2xl">{t('admin.sponsors.detail.recordHint')}</p>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              {/* One gift needs no choice; two or more must be picked, because the wallet is
                  per (sponsor, programme) and the money is not interchangeable. */}
              {creditable.length > 1 ? (
                <label className="flex flex-col gap-1 text-xs text-ground-600">
                  {t('admin.sponsors.detail.programme')}
                  <select
                    value={form.programme_id || String(creditable[0].programme_id)}
                    onChange={(e) => setForm({ ...form, programme_id: e.target.value })}
                    className={inputCls}
                  >
                    {creditable.map((p) => (
                      <option key={p.programme_id} value={p.programme_id}>{p.programme_name}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="flex flex-col gap-1 text-xs text-ground-600">
                  {t('admin.sponsors.detail.programme')}
                  <span className="py-1.5 text-sm text-ground-900">{creditable[0].programme_name}</span>
                </div>
              )}
              <label className="flex flex-col gap-1 text-xs text-ground-600">
                {t('admin.sponsors.detail.amount')} (RM)
                <input
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  inputMode="decimal"
                  placeholder="10000"
                  className={`${inputCls} w-32 tabular-nums`}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-ground-600">
                {t('admin.sponsors.detail.bankRef')}
                <input
                  value={form.external_reference}
                  onChange={(e) => setForm({ ...form, external_reference: e.target.value })}
                  maxLength={100}
                  placeholder="TRF-88214"
                  className={`${inputCls} w-44 font-mono`}
                />
              </label>
              <div className="flex gap-2">
                <button
                  onClick={submitRecord}
                  disabled={busy || !form.amount.trim() || !form.external_reference.trim()}
                  className="rounded-lg bg-brand-fill px-4 py-1.5 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50"
                >
                  {t('admin.sponsors.detail.recordSave')}
                </button>
                <button
                  onClick={() => { setRecording(false); setCreditError('') }}
                  className="rounded-lg border px-3 py-1.5 text-sm text-ground-600 hover:bg-ground-0"
                >
                  {t('common.cancel')}
                </button>
              </div>
            </div>
          </div>
        )}

        {detail.credits.length === 0 ? (
          <p className="px-4 sm:px-5 py-5 text-sm text-ground-500">{t('admin.sponsors.detail.noCredits')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[680px]">
              <thead className="bg-ground-50/80 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.detail.received')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.detail.bankRef')}</th>
                  <th className="text-right px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.detail.amount')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.detail.signOff')}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {pagedCredits.rows.map((c) => {
                  const actions = creditActions(c, detail.finance_check_required, viewerRole)
                  return (
                  <tr key={c.id} className="align-top">
                    <td className="px-4 py-3 whitespace-nowrap text-ground-600">{formatDate(c.created_at)}</td>
                    <td className="px-4 py-3 font-mono text-[12.5px] text-ground-600">{c.external_reference || '—'}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{money(c.amount)}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${creditBadge(c.status)}`}>
                        {t(`admin.sponsors.detail.creditStatus.${c.status}`)}
                      </span>
                      <div className="mt-1.5 flex flex-col gap-0.5 text-xs text-ground-500">
                        {creditChain(c, detail.finance_check_required).map((step) => (
                          <span key={step.key}>
                            <span className={step.done ? 'text-positive-600 font-bold' : 'text-caution-600 font-bold'}>
                              {step.done ? '✓' : '◷'}
                            </span>{' '}
                            {step.done
                              ? t(`admin.sponsors.detail.chain.${step.key}Done`, {
                                  who: step.by || '—',
                                  date: step.at ? formatDate(step.at) : '—',
                                })
                              : t(`admin.sponsors.detail.chain.${step.key}Pending`)}
                          </span>
                        ))}
                      </div>

                      {/* The signature is typed, per row, and checked against the caller's own
                          admin record server-side — a click alone is not a signature. */}
                      {actions.canSign && (
                        <div className="mt-2">
                          <p className="text-[11px] text-ground-500">{t('admin.sponsors.detail.typedNameHint')}</p>
                          <div className="mt-1 flex gap-2">
                            <input
                              value={typedNames[c.id] || ''}
                              onChange={(e) => setTypedNames({ ...typedNames, [c.id]: e.target.value })}
                              placeholder={t('admin.sponsors.detail.fullName')}
                              aria-label={t('admin.sponsors.detail.fullName')}
                              className={`${inputCls} w-44`}
                            />
                            <button
                              onClick={() => runCreditAction(() => signSponsorCredit(c.id, typedNames[c.id] || '', { token: token! }))}
                              disabled={busy || !(typedNames[c.id] || '').trim()}
                              className="rounded-lg bg-brand-fill px-3 py-1.5 text-xs font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50"
                            >
                              {t(`admin.sponsors.detail.sign.${actions.nextStep}`)}
                            </button>
                          </div>
                        </div>
                      )}
                      {/* An org_admin cannot countersign while the finance check is outstanding.
                          Say which step it is waiting on rather than draw a button the server
                          would refuse with `finance_check_required`. */}
                      {actions.blocked === 'awaiting_finance' && (
                        <p className="mt-2 text-[11px] text-caution-700">
                          {t('admin.sponsors.detail.awaitingFinanceCheck')}
                        </p>
                      )}
                      {actions.canVoid && (
                        <button
                          onClick={() => runCreditAction(() => voidSponsorCredit(c.id, { token: token! }))}
                          disabled={busy}
                          className="mt-2 block text-[11px] font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50"
                        >
                          {t('admin.sponsors.detail.void')}
                        </button>
                      )}
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
            <TableFooter paged={pagedCredits} />
          </div>
        )}
      </Block>

      {/* ── what it is funding ───────────────────────────────────────────────── */}
      <Block title={t('admin.sponsors.detail.studentsTitle')} note={t('admin.sponsors.detail.studentsNote')}>
        {detail.sponsorships.length === 0 ? (
          <p className="px-4 sm:px-5 py-5 text-sm text-ground-500">{t('admin.sponsors.detail.noStudents')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[620px]">
              <thead className="bg-ground-50/80 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.detail.offered')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.detail.student')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.detail.programme')}</th>
                  <th className="text-right px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.detail.amount')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.sponsors.status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {pagedStudents.rows.map((s) => (
                  <tr key={s.id}>
                    <td className="px-4 py-3 whitespace-nowrap text-ground-600">
                      {s.offered_at ? formatDate(s.offered_at) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {/* The anonymous code the sponsor sees, so both sides mean the same
                          student; the arrow opens the full application. */}
                      <Link href={`/admin/scholarship/${s.application_id}`}
                        className="font-mono text-[12.5px] text-info-600 hover:text-info-800">
                        {s.ref} →
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-ground-600">{s.programme_name || '—'}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{money(s.amount)}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-ground-600">
                        {t(`admin.sponsors.detail.stage.${studentStage(s.status)}`)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <TableFooter paged={pagedStudents} />
          </div>
        )}
      </Block>

      {/* ── who they brought with them ───────────────────────────────────────── */}
      <Block title={t('admin.sponsors.detail.invitedTitle', { count: String(detail.referrals.length) })}>
        {detail.referrals.length === 0 ? (
          <p className="px-4 sm:px-5 py-5 text-sm text-ground-500">{t('admin.sponsors.detail.noInvites')}</p>
        ) : (
          <ul className="divide-y">
            {pagedReferrals.rows.map((r) => (
              <li key={r.id} className="flex items-baseline justify-between gap-4 px-4 sm:px-5 py-2.5 text-sm">
                <span>
                  <b className="font-medium text-ground-900">{r.invitee_name || '—'}</b>{' '}
                  <span className="text-ground-500">{r.invitee_email || t('admin.sponsors.detail.scrubbed')}</span>
                </span>
                <span className="text-xs text-ground-500 whitespace-nowrap">
                  {r.status === 'joined' && r.joined_at
                    ? t('admin.sponsors.detail.joinedOn', { date: formatDate(r.joined_at) })
                    : t(`admin.sponsors.detail.invite.${r.status}`)}
                </span>
              </li>
            ))}
          </ul>
        )}
        <TableFooter paged={pagedReferrals} />
      </Block>

      {/* ── which gifts they may fund ────────────────────────────────────────
          The panel that unblocks the money. `record_admin_credit` refuses
          `sponsor_not_in_programme` without an approved row here, so before this existed a
          second gift's first benefactor needed an engineer writing SQL.

          Every gift is listed, including the ones they are NOT in — that is the case the
          panel is for. A read-only list of held memberships (what stood here before) could
          only ever restate the status quo. */}
      {gifts.length > 0 && (
        <Block
          title={t('admin.sponsors.detail.membershipsTitle')}
          note={t('admin.sponsors.detail.giftsNote')}
        >
          {giftError && (
            <p className="px-4 sm:px-5 pt-3 text-sm text-critical-600">{giftError}</p>
          )}
          <ul className="divide-y">
            {gifts.map((g) => (
              <li key={g.programme_id}
                  className="flex items-center justify-between gap-4 flex-wrap px-4 sm:px-5 py-3 text-sm">
                <span className="text-ground-900">
                  {g.programme_name}
                  {/* A gift is created switched off and staffed before it opens, so say so
                      rather than let a blank imply it is taking applicants. */}
                  {!g.is_active && (
                    <span className="ml-2 text-xs text-ground-500">
                      {t('admin.sponsors.detail.giftNotOpen')}
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-3">
                  <span className="text-xs text-ground-500">
                    {g.status
                      ? t(`admin.sponsors.detail.giftStatus.${g.status}`)
                      : t('admin.sponsors.detail.giftStatus.none')}
                  </span>
                  {maySetGift && (
                    g.status === 'approved' ? (
                      <button
                        type="button"
                        onClick={() => setGift(g.programme_id, 'rejected')}
                        disabled={giftBusy !== 0}
                        className="text-xs px-3 py-1.5 rounded-lg border text-ground-700 hover:bg-ground-50 disabled:opacity-50"
                      >
                        {t('admin.sponsors.detail.giftTakeBack')}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setGift(g.programme_id, 'approved')}
                        disabled={giftBusy !== 0}
                        className="text-xs px-3 py-1.5 rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
                      >
                        {t('admin.sponsors.detail.giftAccept')}
                      </button>
                    )
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Block>
      )}
    </div>
  )
}
