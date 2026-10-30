'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { useProgrammeParam } from '@/lib/programmeScope'
import { SOURCE_STAGES, levelLabelKey, stageLabelKey } from '@/lib/sourceConsole'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '@/lib/tableView'
import { useGiftInUrl } from '@/lib/useGiftInUrl'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import { Pagination } from '@/components/Pagination'
import { getSourceApplications, type SourceApplicationList } from '@/lib/admin-api'
import { Footnote, K, PageTitle, StageBadge, useSourceName } from './shared'

const COLS = ['student', 'school', 'level', 'sent', 'stage'] as const

/**
 * A source's Applications (source sign-in S3): only the students whose application named this
 * source, read only. Search is by NAME (the server never matches an NRIC, a phone or an email);
 * the stage filter takes the server's own stage keys; the server pages.
 */
export default function SourceApplications() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const source = useSourceName()
  const programme = useProgrammeParam()
  const urlRead = useGiftInUrl()

  const [typed, setTyped] = useState('')
  const [q, setQ] = useState('')
  const [stage, setStage] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [data, setData] = useState<SourceApplicationList | null>(null)
  const [error, setError] = useState(false)

  // The search box settles before it asks (a request per keystroke would race itself).
  useEffect(() => {
    const id = setTimeout(() => { setQ(typed.trim()); setPage(1) }, 300)
    return () => clearTimeout(id)
  }, [typed])

  const latest = useRef(0)
  useEffect(() => {
    if (!urlRead || !token) return
    const ticket = ++latest.current
    setError(false)
    getSourceApplications({ p: programme, q, stage, page, page_size: pageSize }, { token })
      .then((d) => { if (ticket === latest.current) setData(d) })
      .catch(() => { if (ticket === latest.current) setError(true) })
  }, [token, programme, q, stage, page, pageSize, urlRead])

  const rows = data?.applications ?? []

  return (
    <div data-testid="source-applications">
      <PageTitle title={t('admin.scholarship.nav')} subtitle={t(`${K}.applications.subtitle`, { source })} />

      <div className="mb-4 flex flex-wrap gap-2">
        <input type="search" value={typed} onChange={(e) => setTyped(e.target.value)}
          aria-label={t(`${K}.applications.search`)} placeholder={t(`${K}.applications.search`)}
          className="w-full rounded-lg border border-ground-300 px-3 py-2 text-sm sm:w-72" />
        <select value={stage} aria-label={t(`${K}.applications.stageFilter`)}
          onChange={(e) => { setStage(e.target.value); setPage(1) }}
          className="rounded-lg border border-ground-300 bg-ground-0 px-3 py-2 text-sm">
          <option value="">{t(`${K}.applications.allStages`)}</option>
          {SOURCE_STAGES.map((s) => <option key={s} value={s}>{t(stageLabelKey(s))}</option>)}
        </select>
      </div>

      {error && <p className="mb-4 text-sm text-critical-600" role="alert">{t(`${K}.applications.error`)}</p>}

      <TableFrame minWidth={720} label={t('admin.scholarship.nav')}>
        <table className="w-full text-sm">
          <thead className="border-b bg-ground-50">
            <tr>{COLS.map((c) => <th key={c} className={TH}>{t(`${K}.applications.col.${c}`)}</th>)}</tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((a) => (
              <tr key={a.id}>
                <td className="px-4 py-3">
                  <Link href={`/admin/scholarship/${a.id}`} className="font-semibold text-primary-600 hover:underline">
                    {a.student_name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-ground-700">{a.school || '—'}</td>
                <td className="px-4 py-3 text-ground-700">{t(levelLabelKey(a.level))}</td>
                <td className="px-4 py-3 whitespace-nowrap text-ground-500">{formatDate(a.submitted_at) || '—'}</td>
                <td className="px-4 py-3"><StageBadge stage={a.stage} t={t} /></td>
              </tr>
            ))}
            {data && rows.length === 0 && (
              <tr><td colSpan={COLS.length} className="px-4 py-6 text-center text-ground-400">
                {t(q || stage ? `${K}.applications.emptySearch` : `${K}.applications.empty`)}
              </td></tr>
            )}
            {!data && !error && (
              <tr><td colSpan={COLS.length} className="px-4 py-6 text-center text-ground-400">{t('common.loading')}</td></tr>
            )}
          </tbody>
        </table>
      </TableFrame>
      {data && (
        <Pagination page={data.page} totalPages={data.total_pages} pageSize={pageSize}
          onPageChange={setPage} pageSizeOptions={PAGE_SIZE_OPTIONS}
          onPageSizeChange={(n) => { setPageSize(n); setPage(1) }} />
      )}

      <Footnote>{t(`${K}.applications.footnote`)}</Footnote>
    </div>
  )
}
