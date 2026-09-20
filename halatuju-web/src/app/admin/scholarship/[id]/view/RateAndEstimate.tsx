'use client'

/**
 * THE RIGHT COLUMN ABOVE THE DECISION — the officer's Pass/Fail over the AI's four-fact read,
 * the estimated need and proposed bursary, and the by-hand reporting date for an offer letter
 * that carries none.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was. The
 * Decision / Recommendation panel BELOW these did NOT move: untangling it is design work, not a
 * move (roadmap, Phase 4).
 */
import type { Dispatch, SetStateAction } from 'react'
import {
  aiSuggestionFor,
  showsDecisionCards,
  showsPostSubmissionCards,
  showsReportingDateBox,
} from '@/lib/officerCockpit'
import { formatDate } from '@/lib/formatDate'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import type { T } from './shared'

export function RateAndEstimate({
  app, t, busy, canWrite, decisionReopened, decisionRecorded, decisionLocked,
  officerVerdict, setOfficerVerdict,
  reportingDateInput, setReportingDateInput, reportingDateMsg, doSetReportingDate,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  canWrite: boolean
  decisionReopened: boolean
  decisionRecorded: boolean
  decisionLocked: boolean
  officerVerdict: Record<string, string>
  setOfficerVerdict: Dispatch<SetStateAction<Record<string, string>>>
  reportingDateInput: string
  setReportingDateInput: Dispatch<SetStateAction<string>>
  reportingDateMsg: string
  doSetReportingDate: () => void
}) {
  return (<>

      {/* ── Rate AI verification — the officer's Pass/Fail over the AI's four-fact read +
           the AI's suggested verdict. Split out of the old Decision card (2026-07-04) into its
           own topmost box. Both modes: buttons while deciding, badges once recorded. ───────── */}
      {/* Hidden at shortlisted (pre-submission): its rating can only be saved with the verdict.
          Hidden on a CLOSED case with no verdict, for the same reason at the other end. */}
      {showsDecisionCards({ status: app.status, decisionReopened, decisionRecorded }) && (
      <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.recordVerdict.rateTitle')}</h2>
        <div className="space-y-2">
          {(['identity', 'academic', 'pathway', 'income'] as const).map((fact) => (
            decisionLocked ? (
              <div key={fact} className="flex items-center justify-between gap-2 rounded-lg border border-ground-100 p-2.5">
                <span className="text-sm font-medium text-ground-700">{t(`admin.scholarship.verdict.fact.${fact}`)}</span>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  officerVerdict[fact] === 'pass' ? 'bg-positive-100 text-positive-700'
                  : officerVerdict[fact] === 'fail' ? 'bg-critical-100 text-critical-700' : 'bg-ground-100 text-ground-500'}`}>
                  {officerVerdict[fact] === 'pass' ? t('admin.scholarship.recordVerdict.factPass')
                    : officerVerdict[fact] === 'fail' ? t('admin.scholarship.recordVerdict.factFail') : '—'}
                </span>
              </div>
            ) : (
              <div key={fact} className="flex items-center justify-between gap-2 rounded-lg border border-ground-100 p-2.5">
                <span className="text-sm font-medium text-ground-700">{t(`admin.scholarship.verdict.fact.${fact}`)}</span>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => setOfficerVerdict((v) => ({ ...v, [fact]: officerVerdict[fact] === 'pass' ? '' : 'pass' }))}
                    disabled={!canWrite}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      officerVerdict[fact] === 'pass'
                        ? 'border-positive-fill bg-positive-fill text-positive-fill-ink'
                        : 'border-ground-300 text-ground-600 hover:border-positive-400'
                    } disabled:opacity-50`}
                  >
                    {t('admin.scholarship.recordVerdict.factPass')}
                  </button>
                  <button
                    onClick={() => setOfficerVerdict((v) => ({ ...v, [fact]: officerVerdict[fact] === 'fail' ? '' : 'fail' }))}
                    disabled={!canWrite}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      officerVerdict[fact] === 'fail'
                        ? 'border-critical-fill bg-critical-fill text-critical-fill-ink'
                        : 'border-ground-300 text-ground-600 hover:border-critical-400'
                    } disabled:opacity-50`}
                  >
                    {t('admin.scholarship.recordVerdict.factFail')}
                  </button>
                </div>
              </div>
            )
          ))}
        </div>
        {/* AI's suggested verdict — the officer decides; this is the AI's read. */}
        {(() => {
          const sugg = aiSuggestionFor(app.verdict || [])
          const facts = ['identity', 'academic', 'pathway', 'income'] as const
          return (
            <p className="text-[11px] text-ground-400">
              {t('admin.scholarship.recordVerdict.aiSuggested')}{' '}
              {facts.map((f, i) => (
                <span key={f}>
                  {i > 0 && ', '}
                  {t(`admin.scholarship.verdict.fact.${f}`)}{' '}
                  <span className={
                    sugg[f] === 'yes' ? 'text-positive-700 font-medium'
                    : sugg[f] === 'no' ? 'text-critical-600 font-medium'
                    : 'text-caution-700 font-medium'
                  }>
                    {t(`admin.scholarship.recordVerdict.suggest.${sugg[f]}`)}
                  </span>
                </span>
              ))}{'.'}
            </p>
          )
        })()}
      </div>
      )}

      {/* ── Estimated need & proposed bursary — per-pathway estimated GAP after government
           coverage, PLUS the proposed bursary amount (moved out of the old Decision card). ── */}
      {(() => {
        const fe = app.funding_estimate
        const showBursary = app.award_amount != null || app.proposed_award_amount != null
        // Hidden at shortlisted (pre-submission): a projection with no decision attached —
        // the bursary figure is set at the verdict.
        if (!showsPostSubmissionCards(app.status)) return null
        if (!fe && !showBursary) return null
        return (
          <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
            <h2 className="font-semibold">{t('admin.scholarship.estimate.title')}</h2>
            {fe ? (fe.known ? (
              <>
                {/* Total + its monthly breakdown are one tight unit — grouped so the card's
                    space-y doesn't push them apart. */}
                <div>
                  <p className="text-2xl font-semibold text-ground-900">
                    ≈ RM {fe.total.toLocaleString('en-US')}
                  </p>
                  <p className="text-xs text-ground-500">
                    ~RM {fe.monthly.toLocaleString('en-US')}/{t('admin.scholarship.estimate.month')} × {fe.months} {t('admin.scholarship.estimate.months')}
                  </p>
                </div>
                <p className="text-sm text-ground-600">
                  {t(`admin.scholarship.estimate.pathway.${fe.pathway}`)}
                </p>
                {fe.variable && (
                  <p className="mt-2 text-xs text-caution-700">{t('admin.scholarship.estimate.variableNote')}</p>
                )}
                {fe.practical && (
                  <p className="mt-1 text-xs text-ground-500">{t('admin.scholarship.estimate.practicalNote')}</p>
                )}
              </>
            ) : (
              <p className="text-sm text-ground-500">{t('admin.scholarship.estimate.none')}</p>
            )) : null}
            {/* Standard bursary — FIXED by pathway type (RM2k · RM3k STPM · RM1k continuing STPM),
                the same figure for everyone incl. a likely-declined student. No slider: the amount
                is not a reviewer choice (award.py). Prefer the committed award_amount, else the
                pathway figure. A confident disqualifier no longer zeroes it — it shows as a red
                fact in Rate AI verification instead. */}
            {(() => {
              const amt = app.award_amount != null
                ? Math.round(Number(app.award_amount))
                : (app.proposed_award_amount != null ? Math.round(Number(app.proposed_award_amount)) : null)
              if (amt == null) return null
              return (
                <div className="flex items-center justify-between border-t pt-3 text-sm">
                  <span className="font-medium text-ground-600">{t('admin.scholarship.recordVerdict.assistanceLabel')}</span>
                  <span className="font-semibold text-ground-900">RM{amt.toLocaleString()}</span>
                </div>
              )
            })()}
          </div>
        )
      })()}

      {/* ── Reporting date — directly ABOVE Recommendation (owner 2026-07-23) so the reviewer
            meets the empty field while deciding, and most cases are settled before they ever
            reach QC. QC's refusal is the backstop, not the normal route.
            Shown only when the offer letter carries NO readable date, and only in the reviewer's
            window (interviewing, or a reopened case) — `showsReportingDateBox`. ─────────────── */}
      {showsReportingDateBox({
        status: app.status,
        decisionReopened,
        letterHasDate: (app.documents || []).some(
          (d) => d.doc_type === 'offer_letter' && !d.superseded_at && !!d.pathway_check?.reporting_date),
      }) && (
        <div className="rounded-2xl border border-caution-200 bg-ground-0 p-5 shadow-sm space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">
            {t('admin.scholarship.reportingDateEntry.title')}
          </h2>
          <p className="text-xs text-ground-500">{t('admin.scholarship.reportingDateEntry.help')}</p>
          {/* A `type="date"` box carries no accessible name of its own, so a screen reader
              announced nothing here. The heading's own key — nothing on screen changes. */}
          <input
            aria-label={t('admin.scholarship.reportingDateEntry.title')}
            type="date" value={reportingDateInput}
            onChange={(e) => setReportingDateInput(e.target.value)}
            className="w-full rounded-lg border border-ground-300 px-3 py-2 text-sm"
          />
          <button type="button" onClick={doSetReportingDate}
            disabled={!!busy || !reportingDateInput}
            className="w-full rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink
                       hover:bg-brand-fill-hover disabled:opacity-50">
            {busy === 'reportingDate' ? t('common.loading') : t('admin.scholarship.reportingDateEntry.save')}
          </button>
          {app.reporting_date && (
            <p className="text-xs text-ground-500">
              {t('admin.scholarship.reportingDateEntry.current', { date: formatDate(app.reporting_date) })}
            </p>
          )}
          {reportingDateMsg && <p className="text-sm text-critical-600">{reportingDateMsg}</p>}
        </div>
      )}

  </>)
}
