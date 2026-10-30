'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useProgrammeParam } from '@/lib/programmeScope'
import { contractStageKey, scholarStatusKey } from '@/lib/sourceConsole'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '@/lib/tableView'
import { useGiftInUrl } from '@/lib/useGiftInUrl'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import { Pagination } from '@/components/Pagination'
import {
  getSourceOverview, getSourceScholars, type SourceScholarList,
} from '@/lib/admin-api'
import { Footnote, K, PageTitle, useGiftList, witnessHref } from './shared'

const COLS = ['scholar', 'institution', 'course', 'status', 'contract'] as const

/**
 * A source's Scholars (source sign-in S3): its students who received the bursary — institution,
 * course, status as the student sees it, and the contract's stage. NO money, payments, results or
 * semesters (the server sends none).
 *
 * ⚠ "YOUR WITNESS NEEDED" COMES FROM THE OVERVIEW'S `witness_waiting`, the server's one predicate
 * (`source_console.can_witness`): a scholar row carries only the contract's stage, and a stage is
 * not the same question as "is it waiting for THIS source". One extra `admin/source/` read, never
 * a guess from the stage.
 */
export default function SourceScholars() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const programme = useProgrammeParam()
  const urlRead = useGiftInUrl()
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const { page, setPage, data, setData } = useGiftList<SourceScholarList>(programme)
  const [waiting, setWaiting] = useState<Set<number>>(new Set())
  const [error, setError] = useState(false)

  const latest = useRef(0)
  useEffect(() => {
    if (!urlRead || !token) return
    const ticket = ++latest.current
    setError(false)
    getSourceScholars({ p: programme, page, page_size: pageSize }, { token })
      .then((d) => { if (ticket === latest.current) setData(d, programme) })
      .catch(() => { if (ticket === latest.current) setError(true) })
  }, [token, programme, page, pageSize, urlRead, setData])

  // The same ticket for the witness list (review L7): a slow reply for the gift you left must not
  // mark this gift's rows "Your witness needed".
  const latestWaiting = useRef(0)
  useEffect(() => {
    if (!urlRead || !token) return
    const ticket = ++latestWaiting.current
    setWaiting(new Set())
    getSourceOverview(programme, { token })
      .then((o) => {
        if (ticket === latestWaiting.current) setWaiting(new Set(o.witness_waiting.map((w) => w.application_id)))
      })
      .catch(() => { if (ticket === latestWaiting.current) setWaiting(new Set()) })
  }, [token, programme, urlRead])

  const rows = data?.scholars ?? []
  return (
    <div data-testid="source-scholars">
      <PageTitle title={t('admin.scholars.nav')} subtitle={t(`${K}.scholars.subtitle`)} />
      {error && <p className="mb-4 text-sm text-critical-600" role="alert">{t(`${K}.scholars.error`)}</p>}
      <TableFrame minWidth={760} label={t('admin.scholars.nav')}>
        <table className="w-full text-sm">
          <thead className="border-b bg-ground-50">
            <tr>{COLS.map((c) => <th key={c} className={TH}>{t(`${K}.scholars.col.${c}`)}</th>)}</tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-3">
                  <Link href={`/admin/scholars/${s.id}`} className="font-semibold text-primary-600 hover:underline">
                    {s.student_name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-ground-700">{s.institution || '—'}</td>
                <td className="px-4 py-3 text-ground-700">{s.course || '—'}</td>
                <td className="px-4 py-3 text-ground-700">{t(scholarStatusKey(s.status))}</td>
                <td className="px-4 py-3">
                  {waiting.has(s.id) ? (
                    <Link href={witnessHref(s.id)} className="font-semibold text-primary-600 hover:underline">
                      {t(`${K}.scholars.witnessNeeded`)}
                    </Link>
                  ) : <span className="text-ground-700">{t(contractStageKey(s.contract_stage))}</span>}
                </td>
              </tr>
            ))}
            {data && rows.length === 0 && (
              <tr><td colSpan={COLS.length} className="px-4 py-6 text-center text-ground-400">{t(`${K}.scholars.empty`)}</td></tr>
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
      <Footnote>{t(`${K}.scholars.footnote`)}</Footnote>
    </div>
  )
}
