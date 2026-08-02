'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { getReviewerDetail, type AdminReviewerDetail } from '@/lib/admin-api'
import { canAccess, effectiveRole } from '@/lib/navigation'
import {
  credentialLines, hasNoHistory, orderedLanguages, outcomeSegments, phoneState, turnaroundBand,
} from '@/lib/reviewerDetail'

// One reviewer, whole (request #10). What they carry, what became of what they decided, and every
// decision of theirs that was reopened — each with the reason recorded at the time.
//
// ⚠ The reopens block is the reason this page exists rather than a wider table. Seventeen of
// BrightPath's sixty-five decisions carry a reopen and several were caused by OUR defects, not by
// anybody's judgement. The number alone would be read as a competence score; the reason is what
// tells the two apart, so the two never appear separately.
//
// ⚠ `ReviewerProfile` also holds a HOME ADDRESS. It is not in the payload and must not be added:
// assigning a case is not a reason to read where somebody lives (role-matrix.md, 2026-08-02).

function Block({ title, children, note }: {
  title: string
  children: React.ReactNode
  note?: string
}) {
  return (
    <section className="bg-white rounded-xl shadow-sm border overflow-hidden">
      <div className="px-4 sm:px-5 py-3.5 border-b">
        <h2 className="text-[11.5px] font-semibold uppercase tracking-wider text-gray-600">{title}</h2>
      </div>
      {children}
      {note && <p className="px-4 sm:px-5 py-3 text-xs text-gray-500 max-w-3xl">{note}</p>}
    </section>
  )
}

function Figure({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="px-4 sm:px-5 py-4">
      <div className="text-[11px] uppercase tracking-wider text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold tabular-nums mt-1 ${tone ?? 'text-gray-900'}`}>
        {value}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 px-4 sm:px-5 py-2.5 text-sm">
      <div className="w-44 shrink-0 text-gray-500">{label}</div>
      <div className="text-gray-900">{value}</div>
    </div>
  )
}

export default function AdminReviewerDetailPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const params = useParams<{ id: string }>()
  const id = Number(params?.id)
  // The list route, not this one — `canAccess` resolves a detail page to its parent item, and the
  // two carry the same role set by construction. UX only; the endpoint is the fence.
  const mayView = canAccess('/admin/organisation/reviewers', effectiveRole(role))

  const [detail, setDetail] = useState<AdminReviewerDetail | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!token || !id) return
    getReviewerDetail(id, { token })
      .then(setDetail)
      .catch(() => setError(t('admin.reviewers.detail.loadFailed')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  useEffect(() => { load() }, [load])

  if (role && !mayView) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>
  if (error) return <div className="text-red-600">{error}</div>
  if (!detail) return <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>

  const band = turnaroundBand(detail.turnaround_days)
  const segments = outcomeSegments(detail)
  const credentials = credentialLines(detail)
  const phone = phoneState(detail)
  const languages = orderedLanguages(detail)

  return (
    <div className="space-y-5">
      <div>
        <Link href="/admin/organisation/reviewers"
          className="text-sm text-blue-600 hover:text-blue-800">
          ← {t('admin.reviewers.detail.back')}
        </Link>
        <h1 className="text-xl sm:text-2xl font-bold mt-2">{detail.name || detail.email}</h1>
        <p className="text-sm text-gray-500 mt-1">
          {t(`admin.reviewers.role.${detail.role}`)}
          {' · '}
          {t(`admin.reviewers.status.${detail.paused ? 'paused' : 'active'}`)}
          {' · '}
          {t('admin.reviewers.detail.joined', { date: formatDate(detail.created_at) })}
        </p>
      </div>

      <Block title={t('admin.reviewers.detail.workload')}
        note={hasNoHistory(detail) ? t('admin.reviewers.detail.noHistory') : undefined}>
        <div className="grid grid-cols-2 sm:grid-cols-3 divide-x divide-y sm:divide-y-0 divide-gray-100">
          <Figure label={t('admin.reviewers.colOpen')} value={String(detail.open_now)} />
          <Figure label={t('admin.reviewers.colCompleted')} value={String(detail.completed)} />
          <Figure
            label={t('admin.reviewers.colTurnaround')}
            tone={band === 'waiting' ? 'text-amber-700' : undefined}
            value={band === 'unknown'
              ? t('admin.reviewers.noTurnaround')
              : t('admin.reviewers.days', { days: String(detail.turnaround_days) })}
          />
        </div>
      </Block>

      <Block title={t('admin.reviewers.detail.outcomes')}
        note={detail.decided_by_other > 0
          ? t('admin.reviewers.detail.decidedByOther', { count: String(detail.decided_by_other) })
          : undefined}>
        {segments.length === 0 ? (
          <p className="px-4 sm:px-5 py-4 text-sm text-gray-500">
            {t('admin.reviewers.detail.noOutcomes')}
          </p>
        ) : (
          <div className="px-4 sm:px-5 py-4">
            {/* The bar is the shape; the counts beneath it are the fact. A percentage on its own
                over single-digit caseloads would say "100%" about one decision. */}
            <div className="flex h-2.5 rounded-full overflow-hidden bg-gray-100" aria-hidden>
              {segments.map((s) => (
                <div key={s.key} style={{ width: `${s.pct}%` }}
                  className={s.key === 'progressed' ? 'bg-green-500' : 'bg-gray-400'} />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-1 mt-3 text-sm">
              {segments.map((s) => (
                <span key={s.key} className="text-gray-700">
                  <span className={`inline-block w-2.5 h-2.5 rounded-sm mr-1.5 ${
                    s.key === 'progressed' ? 'bg-green-500' : 'bg-gray-400'}`} />
                  {t(`admin.reviewers.detail.${s.key}`)}
                  {': '}
                  <span className="tabular-nums font-semibold">{s.count}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </Block>

      <Block title={t('admin.reviewers.detail.credentials')}>
        {credentials.length === 0 ? (
          <p className="px-4 sm:px-5 py-4 text-sm text-gray-500">
            {t('admin.reviewers.detail.noCredentials')}
          </p>
        ) : (
          <div className="divide-y divide-gray-100 py-1">
            {credentials.map((c) => (
              <Row key={c.key} label={t(`admin.reviewers.detail.${c.key}`)} value={c.value} />
            ))}
          </div>
        )}
      </Block>

      <Block title={t('admin.reviewers.detail.contact')}
        note={t('admin.reviewers.detail.contactNote')}>
        <div className="divide-y divide-gray-100 py-1">
          <Row label={t('admin.reviewers.detail.email')} value={detail.email || '—'} />
          <Row
            label={t('admin.reviewers.detail.phone')}
            value={phone === 'none'
              ? <span className="text-gray-400">{t('admin.reviewers.detail.phoneNone')}</span>
              : (
                <span>
                  {detail.phone}
                  <span className="text-xs text-gray-500 ml-2">
                    {t(`admin.reviewers.detail.phone_${phone}`)}
                  </span>
                </span>
              )}
          />
          <Row
            label={t('admin.reviewers.colLanguages')}
            value={languages.length === 0
              ? <span className="text-gray-400">—</span>
              : languages.map((c) => t(`admin.reviewers.lang.${c}`)).join(', ')}
          />
        </div>
      </Block>

      <Block title={t('admin.reviewers.detail.reopens')}
        note={t('admin.reviewers.detail.reopensNote')}>
        {detail.reopens.length === 0 ? (
          <p className="px-4 sm:px-5 py-4 text-sm text-gray-500">
            {t('admin.reviewers.detail.noReopens')}
          </p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {detail.reopens.map((r) => (
              <li key={r.id} className="px-4 sm:px-5 py-3.5">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <Link href={`/admin/scholarship/${r.application_id}`}
                    className="text-sm font-medium text-blue-600 hover:text-blue-800">
                    {t('admin.reviewers.detail.application', { id: String(r.application_id) })}
                  </Link>
                  <span className="text-xs text-gray-500">
                    {t('admin.reviewers.detail.reopenedBy', {
                      by: r.reopened_by || '—', date: formatDate(r.at),
                    })}
                  </span>
                </div>
                {/* The reason, always — never a bare count. */}
                <p className="text-sm text-gray-700 mt-1 whitespace-pre-wrap">{r.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </Block>
    </div>
  )
}
