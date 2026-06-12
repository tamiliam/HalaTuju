'use client'

/**
 * AI reliability card (verification-assurance Sprint 3 — the scorekeeper).
 *
 * Shows how often the AI's per-fact suggestion matched the reviewer's recorded Pass/Fail
 * decision — the measured "can you rely on it?" answer. Read-only aggregate, non-identifying.
 * The pairs + the agreement maths already exist server-side (audit.override_metrics); this is
 * just the surface (TD-083). Agreement = 1 − override rate, via the tested verdictReliability().
 */

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { getVerdictMetrics } from '@/lib/admin-api'
import { verdictReliability, type Reliability } from '@/lib/officerCockpit'

function Bar({ value, strong = false }: { value: number; strong?: boolean }) {
  return (
    <div className={`flex-1 overflow-hidden rounded-full bg-gray-200 ${strong ? 'h-2.5' : 'h-2'}`}>
      <div className="h-full rounded-full bg-primary-500" style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  )
}

export default function AiReliabilityCard({ token }: { token: string | null }) {
  const { t } = useT()
  const [r, setR] = useState<Reliability | null>(null)

  useEffect(() => {
    if (!token) return
    getVerdictMetrics({ token })
      .then((m) => setR(verdictReliability(m)))
      .catch(() => setR(null))   // a metrics hiccup must never break the list page
  }, [token])

  if (!r) return null
  const pct = (x: number) => `${Math.round(x * 100)}%`

  return (
    <div className="mb-6 rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
      <h2 className="font-semibold text-gray-900">{t('admin.scholarship.reliability.title')}</h2>
      <p className="mt-0.5 text-sm text-gray-500">
        {t('admin.scholarship.reliability.subtitle', { n: String(r.applications) })}
      </p>
      {r.overall.decided === 0 ? (
        <p className="mt-3 text-sm text-gray-500">{t('admin.scholarship.reliability.empty')}</p>
      ) : (
        <div className="mt-4 space-y-2.5">
          {r.perFact.map((f) => (
            <div key={f.fact} className="flex items-center gap-3">
              <span className="w-28 shrink-0 text-sm text-gray-700">
                {t(`admin.scholarship.verdict.fact.${f.fact}`)}
              </span>
              <Bar value={f.pct} />
              <span className="w-10 shrink-0 text-right text-sm font-semibold text-gray-900">
                {f.decided ? pct(f.pct) : '—'}
              </span>
              <span className="w-16 shrink-0 text-right text-xs text-gray-400">
                {f.decided ? `(${f.agree}/${f.decided})` : ''}
              </span>
            </div>
          ))}
          <div className="!mt-3 flex items-center gap-3 border-t border-gray-100 pt-3">
            <span className="w-28 shrink-0 text-sm font-semibold text-gray-900">
              {t('admin.scholarship.reliability.overall')}
            </span>
            <Bar value={r.overall.pct} strong />
            <span className="w-10 shrink-0 text-right text-sm font-bold text-gray-900">{pct(r.overall.pct)}</span>
            <span className="w-16 shrink-0" />
          </div>
        </div>
      )}
    </div>
  )
}
