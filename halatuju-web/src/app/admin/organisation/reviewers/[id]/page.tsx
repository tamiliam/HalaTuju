'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Fragment, useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import {
  getReviewerDetail, setReviewerPaused, setReviewerProgramme, type AdminReviewerDetail,
} from '@/lib/admin-api'
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
  recommended: 'bg-positive-500',
  // CAUTION, not critical: a reviewer declining a case is not the same event as the case
  // being rejected after review — the next line is that one. Orange sat between the two
  // outside the vocabulary; `caution` says the same thing inside it.
  declined: 'bg-caution-500',
  rejectedAfterReview: 'bg-critical-500',
  awaitingQc: 'bg-ground-400',
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
    <section className="bg-ground-0 rounded-xl shadow-sm border overflow-hidden">
      <div className="px-4 sm:px-5 py-3.5 border-b">
        <h2 className="text-[11.5px] font-semibold uppercase tracking-wider text-ground-600">{title}</h2>
      </div>
      {children}
      {note && <p className="px-4 sm:px-5 py-3 text-xs text-ground-500 max-w-3xl">{note}</p>}
    </section>
  )
}

/** One of the three summary figures in the header strip. Right-aligned so the numbers line up. */
function Figure({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="text-right">
      <div className={`text-xl sm:text-2xl font-semibold tabular-nums leading-tight ${
        tone ?? 'text-ground-900'}`}>
        {value}
      </div>
      <div className="text-[10.5px] font-semibold uppercase tracking-wider text-ground-500 mt-0.5">
        {label}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 px-4 sm:px-5 py-2.5 text-sm">
      <div className="w-44 shrink-0 text-ground-500">{label}</div>
      <div className="text-ground-900">{value}</div>
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
  const [giftError, setGiftError] = useState('')
  // Changing who gets work is staff management, so this is NARROWER than reading the page: an
  // `admin` or `finance` may look, only super/org_admin may act. The endpoint re-gates anyway.
  const viewerRole = effectiveRole(role)
  const mayPause = viewerRole === 'super' || viewerRole === 'org_admin'
  // Same gate, same reason, and deliberately a separate name: pause and gift are two different
  // verbs that happen to share a role today. One constant would tie them together by accident.
  const mayGift = mayPause

  const load = useCallback(() => {
    if (!token || !id) return
    getReviewerDetail(id, { token })
      .then(setDetail)
      .catch(() => setError(t('admin.reviewers.detail.loadFailed')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  useEffect(() => { load() }, [load])

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  if (error) return <div className="text-critical-600">{error}</div>
  if (!detail) return <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>

  const band = turnaroundBand(detail.turnaround_days)
  const segments = outcomeSegments(detail)
  const credentials = credentialLines(detail)
  const phone = phoneState(detail)
  const languages = orderedLanguages(detail)

  return (
    <div className="space-y-3.5">
      <Link href="/admin/organisation/reviewers"
        className="text-sm text-info-600 hover:text-info-800">
        ← {t('admin.reviewers.detail.back')}
      </Link>

      {/* ── 1. Identity + the three figures, in ONE strip ────────────────────────────────
          The figures used to own a full card of their own and left most of it empty. They are a
          SUMMARY of the person, so they belong beside the name, not in a section beneath it.
          (Owner review, 2026-08-02: "it is mostly empty space".) */}
      <section className="bg-ground-0 rounded-xl shadow-sm border px-4 sm:px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-bold truncate">{detail.name || detail.email}</h1>
            <p className="text-sm text-ground-500 mt-1 flex flex-wrap items-center gap-x-1.5">
              <span>{t(`admin.reviewers.role.${detail.role}`)}</span>
              <span aria-hidden>·</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                detail.paused ? 'bg-caution-100 text-caution-700' : 'bg-positive-100 text-positive-700'}`}>
                {t(`admin.reviewers.status.${detail.paused ? 'paused' : 'active'}`)}
              </span>
              <span aria-hidden>·</span>
              <span>{t('admin.reviewers.detail.joined', { date: formatDate(detail.created_at) })}</span>
              {/* ⚠ The pause control sits WITH THE STATUS PILL, because the status is the thing it
                  changes — not in a card, and not in a bordered band of its own. It is one verb.
                  (Owner review, 2026-08-02: "It need not be in its box.") */}
              {mayPause && (<>
                <span aria-hidden>·</span>
                <button type="button" disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    setPauseError('')
                    try {
                      const r = await setReviewerPaused(detail.id, !detail.paused, { token: token! })
                      // Patch just this pair — nothing else on the record moves, so a full
                      // re-fetch would only make the page flicker.
                      setDetail({ ...detail, paused: r.paused, paused_at: r.paused_at })
                    } catch {
                      setPauseError(t('admin.reviewers.detail.pauseFailed'))
                    } finally {
                      setBusy(false)
                    }
                  }}
                  // The reassurance an org_admin needs BEFORE they click — that this is not a
                  // revoke — rides on the control itself. The label already scopes it ("Pause NEW
                  // cases"); this says what it leaves alone.
                  title={t(`admin.reviewers.detail.pauseNote${detail.paused ? 'Paused' : 'Active'}`)}
                  className="font-medium text-info-600 hover:text-info-800 hover:underline disabled:opacity-50">
                  {t(`admin.reviewers.detail.${detail.paused ? 'unpause' : 'pause'}`)}
                </button>
              </>)}
            </p>
            {/* The note earns its line only when it is telling you something you did not choose:
                that a PAUSED reviewer keeps their account and their in-flight interviews. For an
                active one it would be a standing explanation of a link nobody has pressed. */}
            {mayPause && detail.paused && (
              <p className="text-xs text-caution-700 mt-1.5 max-w-2xl">
                {t('admin.reviewers.detail.pauseNotePaused')}
              </p>
            )}
            {pauseError && <p className="text-sm text-critical-600 mt-1.5">{pauseError}</p>}

            {/* ── which gift they cover (S-ASSIGN) ──────────────────────────────────────
                Sits with the role and the status because it is the same kind of fact about
                the person, not a card of its own — the same reasoning that put the pause
                control beside the status pill.

                ⚠ SHOWN ONLY WHEN THERE IS A CHOICE. With one gift every reviewer covers it
                and the row could say only one thing — the owner's own 2026-08-02 ruling on
                this exact column, and it still holds for a one-gift organisation.

                ⚠ BLANK MEANS EVERY GIFT, never "no gift". The option is labelled so, because
                an empty select reads as missing data and this is the live default for all 17
                org-scoped staff. */}
            {/* `?? []` is not defensive noise: web and api are separate Cloud Run services and
                a deploy lands them in whichever order it lands them, so for a few minutes this
                page can be newer than the payload it reads. A missing list must render nothing,
                never throw a white screen over a reviewer's whole record. */}
            {(detail.programmes ?? []).length > 1 && (
              <p className="text-sm text-ground-500 mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
                <span>{t('admin.reviewers.detail.giftLabel')}</span>
                {mayGift ? (
                  <select
                    className="border rounded-lg px-2 py-1 text-sm"
                    value={detail.programme_id ?? ''}
                    disabled={busy}
                    onChange={async (e) => {
                      const next = e.target.value ? Number(e.target.value) : null
                      setBusy(true)
                      setGiftError('')
                      try {
                        const r = await setReviewerProgramme(detail.id, next, { token: token! })
                        // Patch just this pair. Nothing else on the record moves — the gift
                        // narrows who is OFFERED work, it does not touch a case they hold.
                        setDetail({
                          ...detail,
                          programme_id: r.programme_id,
                          programme_name: r.programme_name,
                        })
                      } catch {
                        setGiftError(t('admin.reviewers.detail.giftFailed'))
                      } finally {
                        setBusy(false)
                      }
                    }}
                  >
                    <option value="">{t('admin.reviewers.detail.giftEvery')}</option>
                    {detail.programmes.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                        {!p.is_active ? ` — ${t('admin.reviewers.detail.giftNotOpen')}` : ''}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="font-medium text-ground-700">
                    {detail.programme_name || t('admin.reviewers.detail.giftEvery')}
                  </span>
                )}
              </p>
            )}
            {giftError && <p className="text-sm text-critical-600 mt-1.5">{giftError}</p>}
          </div>
          <div className="flex gap-6 sm:gap-8">
            <Figure label={t('admin.reviewers.colOpen')} value={String(detail.open_now)} />
            <Figure label={t('admin.reviewers.colCompleted')} value={String(detail.completed)} />
            <Figure
              label={t('admin.reviewers.colTurnaround')}
              tone={band === 'waiting' ? 'text-caution-700' : undefined}
              value={band === 'unknown'
                ? t('admin.reviewers.noTurnaround')
                : t('admin.reviewers.days', { days: String(detail.turnaround_days) })}
            />
          </div>
        </div>

      </section>

      {/* ── 2. Outcomes | About, side by side ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_.85fr] gap-3.5">
        <Block title={t('admin.reviewers.detail.outcomes')}
          note={hasNoHistory(detail) ? t('admin.reviewers.detail.noHistory') : undefined}>
          {segments.length === 0 ? (
            <p className="px-4 sm:px-5 py-4 text-sm text-ground-500">
              {t('admin.reviewers.detail.noOutcomes')}
            </p>
          ) : (
            <div className="px-4 sm:px-5 py-4">
              {/* The bar is the shape; the counts beneath it are the fact. A percentage on its own
                  over single-digit caseloads would say "100%" about one decision.
                  ⚠ The four bands PARTITION the decided cases (the server guarantees it), so this
                  bar always reconciles with the Completed figure in the strip above. */}
              <div className="flex h-2.5 rounded-full overflow-hidden bg-ground-100" aria-hidden>
                {segments.map((s) => (
                  <div key={s.key} style={{ width: `${s.pct}%` }} className={OUTCOME_BG[s.key]} />
                ))}
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-3.5 text-sm">
                {segments.map((s) => (
                  <span key={s.key} className="text-ground-700">
                    <span className={`inline-block w-2.5 h-2.5 rounded-sm mr-1.5 ${OUTCOME_BG[s.key]}`} />
                    {t(`admin.reviewers.detail.${s.key}`)}
                    {' '}
                    <span className="tabular-nums font-semibold text-ground-900">{s.count}</span>
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
              <p className="col-span-2 text-sm text-ground-500 -my-1">
                {t('admin.reviewers.detail.noCredentials')}
              </p>
            ) : credentials.map((c) => (
              <Fragment key={c.key}>
                <dt className="text-sm text-ground-500 whitespace-nowrap">
                  {t(`admin.reviewers.detail.${c.key}`)}
                </dt>
                <dd className="m-0 text-sm text-ground-900">{c.value}</dd>
              </Fragment>
            ))}

            <div className="col-span-2 h-px bg-ground-100 my-1" />

            <dt className="text-sm text-ground-500">{t('admin.reviewers.detail.email')}</dt>
            <dd className="m-0 text-sm text-ground-900 break-all">{detail.email || '—'}</dd>

            <dt className="text-sm text-ground-500">{t('admin.reviewers.detail.phone')}</dt>
            <dd className="m-0 text-sm text-ground-900">
              {phone === 'none'
                ? <span className="text-ground-400">{t('admin.reviewers.detail.phoneNone')}</span>
                : (<>
                  {/* ⚠ The country code is added HERE. It is stored without one — /admin/profile
                      keeps +60 as fixed chrome beside the input — so this is display only. */}
                  {displayPhone(detail.phone)}
                  <span className="block text-xs text-ground-500 mt-0.5">
                    {t(`admin.reviewers.detail.phone_${phone}`)}
                  </span>
                </>)}
            </dd>

            <dt className="text-sm text-ground-500">{t('admin.reviewers.colLanguages')}</dt>
            <dd className="m-0 text-sm text-ground-900">
              {languages.length === 0
                ? <span className="text-ground-400">—</span>
                : languages.map((c) => t(`admin.reviewers.lang.${c}`)).join(', ')}
            </dd>
          </dl>
        </Block>
      </div>

      <Block title={t('admin.reviewers.detail.reopens')}
        note={t('admin.reviewers.detail.reopensNote')}>
        {detail.reopens.length === 0 ? (
          <p className="px-4 sm:px-5 py-4 text-sm text-ground-500">
            {t('admin.reviewers.detail.noReopens')}
          </p>
        ) : (
          <ul className="divide-y divide-ground-100">
            {detail.reopens.map((r) => (
              <li key={r.id} className="px-4 sm:px-5 py-3.5">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <Link href={`/admin/scholarship/${r.application_id}`}
                    className="text-sm font-medium text-info-600 hover:text-info-800">
                    {t('admin.reviewers.detail.application', { id: String(r.application_id) })}
                  </Link>
                  <span className="text-xs text-ground-500">
                    {t('admin.reviewers.detail.reopenedBy', {
                      by: r.reopened_by || '—', date: formatDate(r.at),
                    })}
                  </span>
                </div>
                {/* The reason, always — never a bare count. */}
                <p className="text-sm text-ground-700 mt-1 whitespace-pre-wrap">{r.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </Block>
    </div>
  )
}
