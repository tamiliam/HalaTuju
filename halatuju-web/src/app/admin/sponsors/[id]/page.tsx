'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { canVoid, creditChain, hasNoMoney, pendingTotal, seenBand, studentStage } from '@/lib/sponsorDetail'
import { getSponsorDetail, type AdminSponsorDetail } from '@/lib/admin-api'

// One sponsor, whole — the page that did not exist until 2026-07-27. Money first, because
// that is the question you open a sponsor to answer; then what it is funding, then who they
// brought with them.
//
// The ACCOUNT is platform-level and shown in full; the MONEY and the STUDENTS are fenced to
// the caller's organisation server-side. `detail.fenced` tells us to say so rather than let
// an org admin read a partial figure as the sponsor's whole giving record.

const money = (v: string) => Number(v).toLocaleString('en-MY', { minimumFractionDigits: 2 })

const statusBadge = (s: string) =>
  s === 'approved' ? 'bg-green-100 text-green-700'
    : s === 'pending' ? 'bg-amber-100 text-amber-700'
      : s === 'suspended' ? 'bg-orange-100 text-orange-700'
        : 'bg-red-100 text-red-600'

const creditBadge = (s: string) =>
  s === 'confirmed' ? 'bg-green-100 text-green-700'
    : s === 'cancelled' ? 'bg-gray-100 text-gray-500'
      : 'bg-amber-100 text-amber-700'

function Block({ title, action, children, note }: {
  title: string
  action?: React.ReactNode
  children: React.ReactNode
  note?: string
}) {
  return (
    <section className="bg-white rounded-xl shadow-sm border overflow-hidden">
      <div className="flex items-center justify-between gap-4 flex-wrap px-4 sm:px-5 py-3.5 border-b">
        <h2 className="text-[11.5px] font-semibold uppercase tracking-wider text-gray-600">{title}</h2>
        {action}
      </div>
      {children}
      {note && <p className="px-4 sm:px-5 py-3 text-xs text-gray-500 max-w-3xl">{note}</p>}
    </section>
  )
}

export default function AdminSponsorDetailPage() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const params = useParams<{ id: string }>()
  const id = Number(params?.id)

  const [detail, setDetail] = useState<AdminSponsorDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token || !id) return
    getSponsorDetail(id, { token })
      .then(setDetail)
      .catch(() => setError(t('admin.sponsors.detail.loadFailed')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  if (error) return <div className="text-red-600">{error}</div>
  if (!detail) return <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>

  const pending = pendingTotal(detail.credits)

  return (
    <div className="max-w-5xl font-plex flex flex-col gap-5">
      <Link href="/admin/sponsors" className="text-xs text-gray-500 hover:text-blue-600">
        ← {t('admin.sponsors.title')}
      </Link>

      {/* ── who they are ─────────────────────────────────────────────────────── */}
      <section className="bg-white rounded-xl shadow-sm border px-4 sm:px-5 py-4 flex flex-col gap-2.5">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-bold text-gray-900">{detail.name || '—'}</h1>
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusBadge(detail.status)}`}>
            {detail.status}
          </span>
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
            {t(`admin.sponsors.detail.digest.${detail.notify_frequency}`)}
          </span>
          {detail.is_trusted && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
              {t('admin.sponsors.detail.trusted')}
            </span>
          )}
        </div>
        <div className="text-sm text-gray-600 flex flex-wrap gap-x-4 gap-y-1">
          <span>{detail.email || '—'}</span>
          {detail.phone && <span>{detail.phone}</span>}
          {detail.organisation && <span>{detail.organisation}</span>}
        </div>
        <div className="text-[13px] text-gray-500 flex flex-wrap gap-x-4 gap-y-1">
          <span>{t('admin.sponsors.detail.registeredOn', { date: formatDate(detail.created_at) })}</span>
          {detail.reviewed_by && (
            <span>{t('admin.sponsors.detail.vettedBy', {
              who: detail.reviewed_by,
              date: detail.reviewed_at ? formatDate(detail.reviewed_at) : '—',
            })}</span>
          )}
          <span
            className={seenBand(detail.last_seen_at) === 'never' || seenBand(detail.last_seen_at) === 'dormant'
              ? 'text-amber-700 font-medium' : ''}
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
        {detail.note && <p className="text-sm text-gray-600 whitespace-pre-wrap">{detail.note}</p>}
      </section>

      {/* ── the money, one wallet per gift programme ─────────────────────────── */}
      {detail.fenced && (
        <p className="text-xs text-gray-500">{t('admin.sponsors.detail.fencedNote')}</p>
      )}

      {hasNoMoney(detail) ? (
        <Block title={t('admin.sponsors.detail.walletTitle')}>
          <p className="px-4 sm:px-5 py-5 text-sm text-gray-500">
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
              <div key={key} className={`rounded-lg border p-3.5 ${key === 'available' ? 'bg-blue-50 border-transparent' : 'bg-gray-50'}`}>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                  {t(`admin.sponsors.detail.${key}`)}
                </div>
                <div className={`text-2xl font-bold tabular-nums ${key === 'available' ? 'text-blue-700' : 'text-gray-900'}`}>
                  RM {money(value)}
                </div>
                {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
              </div>
            ))}
          </div>
        </Block>
      ))}

      {pending > 0 && (
        <p className="flex items-baseline gap-2.5 rounded-lg bg-amber-50 border border-amber-200 px-4 py-2.5 text-sm text-amber-700">
          <span aria-hidden>◆</span>
          <span>{t('admin.sponsors.detail.pendingCaveat', { amount: money(String(pending)) })}</span>
        </p>
      )}

      {/* ── wallet credits + their sign-off chain ────────────────────────────── */}
      <Block title={t('admin.sponsors.detail.creditsTitle')} note={t('admin.sponsors.detail.creditsNote')}>
        {detail.credits.length === 0 ? (
          <p className="px-4 sm:px-5 py-5 text-sm text-gray-500">{t('admin.sponsors.detail.noCredits')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[680px]">
              <thead className="bg-gray-50/80 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.detail.received')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.detail.bankRef')}</th>
                  <th className="text-right px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.detail.amount')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.detail.signOff')}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {detail.credits.map((c) => (
                  <tr key={c.id} className="align-top">
                    <td className="px-4 py-3 whitespace-nowrap text-gray-600">{formatDate(c.created_at)}</td>
                    <td className="px-4 py-3 font-mono text-[12.5px] text-gray-600">{c.external_reference || '—'}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{money(c.amount)}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${creditBadge(c.status)}`}>
                        {t(`admin.sponsors.detail.creditStatus.${c.status}`)}
                      </span>
                      <div className="mt-1.5 flex flex-col gap-0.5 text-xs text-gray-500">
                        {creditChain(c, detail.finance_check_required).map((step) => (
                          <span key={step.key}>
                            <span className={step.done ? 'text-green-600 font-bold' : 'text-amber-600 font-bold'}>
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
                      {/* Recording, signing and voiding arrive in S2 — this sprint reads only,
                          so no button is drawn that the endpoint would then have to refuse. */}
                      {canVoid(c) && (
                        <div className="mt-1 text-[11px] text-gray-400">
                          {t('admin.sponsors.detail.actionsSoon')}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Block>

      {/* ── what it is funding ───────────────────────────────────────────────── */}
      <Block title={t('admin.sponsors.detail.studentsTitle')} note={t('admin.sponsors.detail.studentsNote')}>
        {detail.sponsorships.length === 0 ? (
          <p className="px-4 sm:px-5 py-5 text-sm text-gray-500">{t('admin.sponsors.detail.noStudents')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[620px]">
              <thead className="bg-gray-50/80 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.detail.offered')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.detail.student')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.detail.programme')}</th>
                  <th className="text-right px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.detail.amount')}</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">{t('admin.sponsors.status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {detail.sponsorships.map((s) => (
                  <tr key={s.id}>
                    <td className="px-4 py-3 whitespace-nowrap text-gray-600">
                      {s.offered_at ? formatDate(s.offered_at) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {/* The anonymous code the sponsor sees, so both sides mean the same
                          student; the arrow opens the full application. */}
                      <Link href={`/admin/scholarship/${s.application_id}`}
                        className="font-mono text-[12.5px] text-blue-600 hover:text-blue-800">
                        {s.ref} →
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{s.programme_name || '—'}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{money(s.amount)}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-gray-600">
                        {t(`admin.sponsors.detail.stage.${studentStage(s.status)}`)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Block>

      {/* ── who they brought with them ───────────────────────────────────────── */}
      <Block title={t('admin.sponsors.detail.invitedTitle', { count: String(detail.referrals.length) })}>
        {detail.referrals.length === 0 ? (
          <p className="px-4 sm:px-5 py-5 text-sm text-gray-500">{t('admin.sponsors.detail.noInvites')}</p>
        ) : (
          <ul className="divide-y">
            {detail.referrals.map((r) => (
              <li key={r.id} className="flex items-baseline justify-between gap-4 px-4 sm:px-5 py-2.5 text-sm">
                <span>
                  <b className="font-medium text-gray-900">{r.invitee_name || '—'}</b>{' '}
                  <span className="text-gray-500">{r.invitee_email || t('admin.sponsors.detail.scrubbed')}</span>
                </span>
                <span className="text-xs text-gray-500 whitespace-nowrap">
                  {r.status === 'joined' && r.joined_at
                    ? t('admin.sponsors.detail.joinedOn', { date: formatDate(r.joined_at) })
                    : t(`admin.sponsors.detail.invite.${r.status}`)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Block>

      {detail.memberships.length > 0 && (
        <Block title={t('admin.sponsors.detail.membershipsTitle')}>
          <ul className="divide-y">
            {detail.memberships.map((m) => (
              <li key={m.programme_name} className="flex items-baseline justify-between gap-4 px-4 sm:px-5 py-2.5 text-sm">
                <span className="text-gray-900">{m.programme_name || '—'}</span>
                <span className="text-xs text-gray-500">
                  {m.status}{m.vetted_by ? ` · ${m.vetted_by}` : ''}
                </span>
              </li>
            ))}
          </ul>
        </Block>
      )}
    </div>
  )
}
