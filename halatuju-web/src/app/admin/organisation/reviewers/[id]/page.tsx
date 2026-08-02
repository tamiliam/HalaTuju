'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Fragment, useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { getReviewerDetail, setReviewerPaused, type AdminReviewerDetail } from '@/lib/admin-api'
import { canAccess, effectiveRole } from '@/lib/navigation'
import {
  credentialLines, displayPhone, hasNoHistory, orderedLanguages, outcomeSegments, phoneState,
  turnaroundBand, type OutcomeKey,
} from '@/lib/reviewerDetail'

/**
 * The colour of each outcome band — one home, so the bar and its legend cannot drift apart.
 *
 * ⚠ Amber and red are DIFFERENT on purpose. Amber is a rejection this reviewer made; red is one
 * somebody else made on a case they reviewed. Painting both the same accuses them of a decision
 * that was not theirs.
 */
const OUTCOME_BG: Record<OutcomeKey, string> = {
  recommended: 'bg-green-500',
  declined: 'bg-orange-500',
  rejectedAfterReview: 'bg-red-500',
  awaitingQc: 'bg-gray-400',
}

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

/** One of the three summary figures in the header strip. Right-aligned so the numbers line up. */
function Figure({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="text-right">
      <div className={`text-xl sm:text-2xl font-semibold tabular-nums leading-tight ${
        tone ?? 'text-gray-900'}`}>
        {value}
      </div>
      <div className="text-[10.5px] font-semibold uppercase tracking-wider text-gray-500 mt-0.5">
        {label}
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
  const [busy, setBusy] = useState(false)
  const [pauseError, setPauseError] = useState('')
  // Changing who gets work is staff management, so this is NARROWER than reading the page: an
  // `admin` or `finance` may look, only super/org_admin may act. The endpoint re-gates anyway.
  const viewerRole = effectiveRole(role)
  const mayPause = viewerRole === 'super' || viewerRole === 'org_admin'

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
    <div className="space-y-3.5">
      <Link href="/admin/organisation/reviewers"
        className="text-sm text-blue-600 hover:text-blue-800">
        ← {t('admin.reviewers.detail.back')}
      </Link>

      {/* ── 1. Identity + the three figures, in ONE strip ────────────────────────────────
          The figures used to own a full card of their own and left most of it empty. They are a
          SUMMARY of the person, so they belong beside the name, not in a section beneath it.
          (Owner review, 2026-08-02: "it is mostly empty space".) */}
      <section className="bg-white rounded-xl shadow-sm border px-4 sm:px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-bold truncate">{detail.name || detail.email}</h1>
            <p className="text-sm text-gray-500 mt-1 flex flex-wrap items-center gap-x-1.5">
              <span>{t(`admin.reviewers.role.${detail.role}`)}</span>
              <span aria-hidden>·</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                detail.paused ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}`}>
                {t(`admin.reviewers.status.${detail.paused ? 'paused' : 'active'}`)}
              </span>
              <span aria-hidden>·</span>
              <span>{t('admin.reviewers.detail.joined', { date: formatDate(detail.created_at) })}</span>
            </p>
          </div>
          <div className="flex gap-6 sm:gap-8">
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
        </div>

        {/* Pause on somebody's behalf — a volunteer who has gone quiet cannot always press their
            own switch, and a control with no way back is a one-way conversation, so the same
            button un-pauses. It rides in this strip rather than owning a card: it is one control
            and one sentence. */}
        {mayPause && (
          <div className="mt-4 pt-4 border-t flex flex-wrap items-center gap-x-4 gap-y-2">
            <button type="button" disabled={busy}
              onClick={async () => {
                setBusy(true)
                setPauseError('')
                try {
                  const r = await setReviewerPaused(detail.id, !detail.paused, { token: token! })
                  // Patch just this pair — nothing else on the record moves, so a full re-fetch
                  // would only make the page flicker.
                  setDetail({ ...detail, paused: r.paused, paused_at: r.paused_at })
                } catch {
                  setPauseError(t('admin.reviewers.detail.pauseFailed'))
                } finally {
                  setBusy(false)
                }
              }}
              className={`rounded-lg px-3.5 py-1.5 text-sm font-semibold text-white disabled:opacity-50 ${
                detail.paused ? 'bg-green-600 hover:bg-green-700' : 'bg-amber-600 hover:bg-amber-700'}`}>
              {t(`admin.reviewers.detail.${detail.paused ? 'unpause' : 'pause'}`)}
            </button>
            <span className="text-xs text-gray-500 max-w-2xl">
              {t(`admin.reviewers.detail.pauseNote${detail.paused ? 'Paused' : 'Active'}`)}
            </span>
            {pauseError && <span className="text-sm text-red-600">{pauseError}</span>}
          </div>
        )}
      </section>

      {/* ── 2. Outcomes | About, side by side ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_.85fr] gap-3.5">
        <Block title={t('admin.reviewers.detail.outcomes')}
          note={hasNoHistory(detail) ? t('admin.reviewers.detail.noHistory') : undefined}>
          {segments.length === 0 ? (
            <p className="px-4 sm:px-5 py-4 text-sm text-gray-500">
              {t('admin.reviewers.detail.noOutcomes')}
            </p>
          ) : (
            <div className="px-4 sm:px-5 py-4">
              {/* The bar is the shape; the counts beneath it are the fact. A percentage on its own
                  over single-digit caseloads would say "100%" about one decision.
                  ⚠ The four bands PARTITION the decided cases (the server guarantees it), so this
                  bar always reconciles with the Completed figure in the strip above. */}
              <div className="flex h-2.5 rounded-full overflow-hidden bg-gray-100" aria-hidden>
                {segments.map((s) => (
                  <div key={s.key} style={{ width: `${s.pct}%` }} className={OUTCOME_BG[s.key]} />
                ))}
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-3.5 text-sm">
                {segments.map((s) => (
                  <span key={s.key} className="text-gray-700">
                    <span className={`inline-block w-2.5 h-2.5 rounded-sm mr-1.5 ${OUTCOME_BG[s.key]}`} />
                    {t(`admin.reviewers.detail.${s.key}`)}
                    {' '}
                    <span className="tabular-nums font-semibold text-gray-900">{s.count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </Block>

        {/* Credentials and Contact were two nearly-empty full-width cards. As one definition list
            they read as a single fact sheet, which is what a reader actually wants from them. */}
        <Block title={t('admin.reviewers.detail.about')}
          note={t('admin.reviewers.detail.contactNote')}>
          <dl className="px-4 sm:px-5 py-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2.5 items-baseline">
            {credentials.length === 0 ? (
              <p className="col-span-2 text-sm text-gray-500 -my-1">
                {t('admin.reviewers.detail.noCredentials')}
              </p>
            ) : credentials.map((c) => (
              <Fragment key={c.key}>
                <dt className="text-sm text-gray-500 whitespace-nowrap">
                  {t(`admin.reviewers.detail.${c.key}`)}
                </dt>
                <dd className="m-0 text-sm text-gray-900">{c.value}</dd>
              </Fragment>
            ))}

            <div className="col-span-2 h-px bg-gray-100 my-1" />

            <dt className="text-sm text-gray-500">{t('admin.reviewers.detail.email')}</dt>
            <dd className="m-0 text-sm text-gray-900 break-all">{detail.email || '—'}</dd>

            <dt className="text-sm text-gray-500">{t('admin.reviewers.detail.phone')}</dt>
            <dd className="m-0 text-sm text-gray-900">
              {phone === 'none'
                ? <span className="text-gray-400">{t('admin.reviewers.detail.phoneNone')}</span>
                : (<>
                  {/* ⚠ The country code is added HERE. It is stored without one — /admin/profile
                      keeps +60 as fixed chrome beside the input — so this is display only. */}
                  {displayPhone(detail.phone)}
                  <span className="block text-xs text-gray-500 mt-0.5">
                    {t(`admin.reviewers.detail.phone_${phone}`)}
                  </span>
                </>)}
            </dd>

            <dt className="text-sm text-gray-500">{t('admin.reviewers.colLanguages')}</dt>
            <dd className="m-0 text-sm text-gray-900">
              {languages.length === 0
                ? <span className="text-gray-400">—</span>
                : languages.map((c) => t(`admin.reviewers.lang.${c}`)).join(', ')}
            </dd>
          </dl>
        </Block>
      </div>

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
