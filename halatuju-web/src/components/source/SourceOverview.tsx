'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { useProgrammeParam } from '@/lib/programmeScope'
import { SOURCE_STAGES, stageLabelKey } from '@/lib/sourceConsole'
import { useGiftInUrl } from '@/lib/useGiftInUrl'
import { getSourceOverview, type SourceOverview as Payload } from '@/lib/admin-api'
import { CARD, Footnote, K, PageTitle, useSourceName, witnessHref } from './shared'

/**
 * A source's Overview (source sign-in S3 + S4): its students' folded stage counts, its scholars,
 * the contracts waiting for its witness, and the partner email's chase list.
 *
 * ⚠ THE GIFT IS THE CRUMB'S, sent as `?p=` — one of the source's own gifts; absent, the server
 * describes every gift the source may see (it never picks one).
 * ⚠ A RESULT SHOWS ONLY ONCE THE STUDENT HAS BEEN TOLD: the counts are the student's own masked
 * stages (C12), which is what the footnote says. Every stage is drawn, so the tiles add up to the
 * total — a partner must never receive numbers that do not.
 */
export default function SourceOverview() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const source = useSourceName()
  const programme = useProgrammeParam()
  const urlRead = useGiftInUrl()
  const [data, setData] = useState<Payload | null>(null)
  const [error, setError] = useState(false)

  // ⚠ ONLY THE NEWEST READ MAY LAND — a slow reply for the gift you left must not overwrite this one.
  const latest = useRef(0)
  useEffect(() => {
    if (!urlRead || !token) return
    const ticket = ++latest.current
    setError(false)
    getSourceOverview(programme, { token })
      .then((d) => { if (ticket === latest.current) setData(d) })
      .catch(() => { if (ticket === latest.current) setError(true) })
  }, [token, programme, urlRead])

  const waiting = data?.witness_waiting ?? []
  const tile = (label: string, n: number, testId: string) => (
    <div key={testId} className={CARD} data-testid={testId}>
      <div className="text-xs text-ground-500">{label}</div>
      <div className="mt-1 text-3xl font-bold text-ground-900">{n}</div>
    </div>
  )

  return (
    <div data-testid="source-overview">
      <PageTitle title={t(`${K}.overview.title`)}
        subtitle={data?.programme
          ? t(`${K}.overview.subtitleFor`, { source, gift: data.programme.name })
          : t(`${K}.overview.subtitle`, { source })} />

      {error && <p className="mb-4 text-sm text-critical-600" role="alert">{t(`${K}.overview.error`)}</p>}
      {!data && !error && <p className="text-sm text-ground-500">{t('common.loading')}</p>}

      {data && (<>
        {waiting.length > 0 && (
          <section data-testid="witness-banner"
            className="mb-5 flex flex-col gap-3 rounded-xl border border-caution-200 bg-caution-50 p-5 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-caution-900">
                {waiting.length === 1 ? t(`${K}.overview.witnessOne`)
                  : t(`${K}.overview.witnessMany`, { n: String(waiting.length) })}
              </p>
              <p className="mt-1 text-sm text-caution-800">
                {waiting.map((w, i) => (
                  <span key={w.application_id}>
                    {i > 0 && ', '}
                    <Link href={witnessHref(w.application_id)} className="font-medium hover:underline">{w.student_name}</Link>
                  </span>
                ))}
                {' — '}{t(`${K}.overview.witnessNote`)}
              </p>
            </div>
            <Link href={witnessHref(waiting[0].application_id)}
              className="shrink-0 rounded-lg bg-brand-fill px-4 py-2.5 text-center text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
              {t(`${K}.overview.witnessNow`)}
            </Link>
          </section>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="stage-tiles">
          {SOURCE_STAGES.map((stage) => tile(t(stageLabelKey(stage)), data.counts[stage] ?? 0, `tile-${stage}`))}
          {tile(t(`${K}.overview.scholars`), data.scholars, 'tile-scholars')}
        </div>
        <p className="mt-2 text-sm text-ground-500" data-testid="overview-total">
          {t(`${K}.overview.total`, { n: String(data.counts.total ?? 0) })}
        </p>

        <section className={`${CARD} mt-5`} data-testid="missing-items">
          <h2 className="mb-2 text-base font-semibold text-ground-900">{t(`${K}.overview.missingTitle`)}</h2>
          {data.missing_items.length === 0 ? (
            <p className="text-sm text-ground-500">{t(`${K}.overview.missingNone`)}</p>
          ) : (
            <ul className="divide-y divide-ground-100 text-sm">
              {data.missing_items.map((m) => (
                <li key={m.application_id} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                  <span>
                    <span className="font-medium text-ground-900">{m.student_name}</span>
                    <span className="ml-2 text-xs text-ground-500">
                      {t(`${K}.overview.missingRow`, { applied: formatDate(m.applied) || '—', active: formatDate(m.last_activity) || '—' })}
                    </span>
                  </span>
                  <Link href={`/admin/scholarship/${m.application_id}`}
                    className="text-sm font-medium text-primary-600 hover:underline">{t(`${K}.overview.open`)}</Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </>)}

      <Footnote>{t(`${K}.overview.toldFootnote`)}</Footnote>
    </div>
  )
}
