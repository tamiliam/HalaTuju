'use client'

/**
 * THE VERIFICATION VERDICT — four horizontal fact tiles with their confidence band, the
 * course-switch banner, the Check-2 case summary and the expanded evidence for whatever is not
 * yet green.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import { factTileTone, TONE_BAND_KEY, verdictItemKey } from '@/lib/officerCockpit'
import { localiseParams } from '@/lib/actionCentre'
import type { AdminScholarshipDetail, AdminVerdictItem, VerdictCaseSummary } from '@/lib/admin-api'

import type { T } from './shared'

export function VerificationVerdict({ app, t, caseSummary }: {
  app: AdminScholarshipDetail
  t: T
  caseSummary: VerdictCaseSummary | null
}) {
  return (<>

      {/* ── Verification verdict — four horizontal tiles ───────────────────────── */}
      <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.verdict.title')}</h2>
            <p className="text-xs text-ground-500">{t('admin.scholarship.verdict.intro')}</p>
          </div>
        </div>
        {/* Horizontal tile row */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(app.verdict || []).map((f) => {
            const tone = factTileTone(f)
            const tileColour = {
              green: 'border-positive-200 bg-positive-50',
              amber: 'border-caution-200 bg-caution-50',
              blue: 'border-primary-200 bg-primary-50',
              red: 'border-critical-200 bg-critical-50',
            }[tone]
            const dotColour = {
              green: 'bg-positive-500',
              amber: 'bg-caution-500',
              blue: 'bg-brand-shape',
              red: 'bg-critical-500',
            }[tone]
            const labelColour = {
              green: 'text-positive-700',
              amber: 'text-caution-700',
              blue: 'text-primary-700',
              red: 'text-critical-700',
            }[tone]
            // Subtitle: first evidence item text, or first unresolved item text.
            const resolve = (it: AdminVerdictItem) =>
              t(`admin.scholarship.verdict.item.${verdictItemKey(it)}`,
                localiseParams(it.params, t))
            const subtitle = f.unresolved.length > 0
              ? resolve(f.unresolved[0])
              : f.evidence.length > 0
              ? resolve(f.evidence[0])
              : t(`admin.scholarship.verdict.status.${f.status}`)
            // A green (verified) fact is done — the tick says it all, so we drop the
            // description (and its detail block below). Amber/red keep the lead line.
            const isGreen = tone === 'green'
            return (
              <div key={f.fact} className={`min-w-0 rounded-lg border p-3 flex flex-col gap-1.5 ${tileColour}`}>
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className={`h-2 w-2 rounded-full shrink-0 ${dotColour}`} aria-hidden />
                  <span className={`truncate text-xs font-semibold uppercase tracking-wide ${labelColour}`}>
                    {t(`admin.scholarship.verdict.fact.${f.fact}`)}
                  </span>
                  {isGreen && (
                    <span className="ml-auto shrink-0 text-positive-700 text-sm font-bold"
                      aria-label={t('admin.scholarship.verdict.status.verified')}>✓</span>
                  )}
                </div>
                {/* The estimative-probability band (Kent scale) the colour stands for. */}
                <p className={`text-[10px] font-semibold uppercase tracking-wide ${labelColour}`}>
                  {t(`admin.scholarship.verdict.band.${TONE_BAND_KEY[tone]}`)}
                </p>
                {!isGreen && (
                  <p className="text-[11px] text-ground-700 leading-tight line-clamp-2 break-words">{subtitle}</p>
                )}
              </div>
            )
          })}
          {(app.verdict || []).length === 0 && (
            <p className="col-span-4 text-sm text-ground-400 italic">{t('admin.scholarship.none')}</p>
          )}
        </div>
        {/* Legend — the confidence scale the tile colours encode (green→red). */}
        {(app.verdict || []).length > 0 && (
          <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-ground-400">
            {(['green', 'blue', 'amber', 'red'] as const).map((tn) => (
              <span key={tn} className="flex items-center gap-1">
                <span className={`h-2 w-2 rounded-full ${ {green:'bg-positive-500',blue:'bg-brand-shape',amber:'bg-caution-500',red:'bg-critical-500'}[tn] }`} aria-hidden />
                {t(`admin.scholarship.verdict.band.${TONE_BAND_KEY[tn]}`)}
              </span>
            ))}
          </div>
        )}
        {/* Course-switch banner (owner 2026-07-10): the live offer replaced a genuinely different
            prior offer (any→any). ALWAYS shown — survives the green-collapse — so a switch is never
            missed. Info (blue) not warning: a PUBLIC switch is acceptable; the pathway tile itself
            (red if it landed on a private/IPTS arm) carries the accept/reject. */}
        {(() => {
          const sw = (app.documents || []).find(
            (d) => d.doc_type === 'offer_letter' && d.pathway_check?.switched_from)
          const from = sw?.pathway_check?.switched_from
          if (!from) return null
          const pc = sw!.pathway_check!
          return (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-primary-100 bg-primary-50 p-2.5 text-xs text-primary-800">
              <span aria-hidden>⇄</span>
              <span>{t('admin.scholarship.verdict.item.pathway_switched', {
                from_programme: from.programme || '—',
                from_institution: from.institution || '—',
                to_programme: pc.programme || '—',
                to_institution: pc.institution || '—',
              })}</span>
            </div>
          )
        })()}
        {/* Check-2 case summary — the LLM briefing that "talks to the reviewer" (dark-flag aware;
            empty when every fact is Certain). Sits above the checklist, which is the audit trail.

            INFO, not a category swatch (Layer 1 F5). The indigo here was picked to say "a model
            wrote this, not a person" — but that is what the panel's own heading says, and the
            panel's JOB is to inform the reviewer. A category colour would have made provenance a
            decorative property of a block of prose. The capture chips further down ARE a category
            (deterministic vs model-derived) and do take a swatch. */}
        {caseSummary?.enabled && (caseSummary.summary || '').trim() && (
          <div className="mt-3 rounded-lg border border-info-100 bg-info-50/60 p-3 text-sm text-ground-700">
            {caseSummary.summary}
          </div>
        )}
        {/* Expanded evidence / unresolved — shown ONLY for facts that still need attention.
            A green fact is hidden here (its tile tick is the whole story). */}
        {(app.verdict || []).some((f) => factTileTone(f) !== 'green' && (f.evidence.length > 1 || f.unresolved.length > 0)) && (
          <div className="mt-3 space-y-2 border-t border-ground-100 pt-3">
            {(app.verdict || []).map((f) => {
              const resolve = (it: AdminVerdictItem) =>
                t(`admin.scholarship.verdict.item.${verdictItemKey(it)}`,
                  localiseParams(it.params, t))
              if (factTileTone(f) === 'green' || (f.evidence.length <= 1 && f.unresolved.length === 0)) return null
              return (
                <div key={`detail-${f.fact}`} className="text-xs text-ground-600">
                  <span className="font-medium text-ground-500 uppercase text-[10px] tracking-wide">
                    {t(`admin.scholarship.verdict.fact.${f.fact}`)}
                  </span>
                  {/* Findings first (the active reasoning — e.g. the STR verdict leads the
                      income story), then the supporting confirmations. */}
                  {f.unresolved.map((it, i) => (
                    <div key={`u${i}`} className="ml-2 flex items-start gap-1 mt-0.5">
                      <span className="text-caution-700 shrink-0">•</span>
                      <span>{resolve(it)}</span>
                    </div>
                  ))}
                  {f.evidence.slice(1).map((it, i) => (
                    <div key={`e${i}`} className="ml-2 flex items-start gap-1 mt-0.5">
                      <span className="text-positive-700 shrink-0">✓</span>
                      <span>{resolve(it)}</span>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>

  </>)
}
