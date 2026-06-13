'use client'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { getCourseDataStatus, runCourseDataCheck, type CourseDataStatusResponse, type LinkFailure } from '@/lib/admin-api'
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'

function fmtDate(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (isNaN(d.getTime())) return null
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function CourseDataDashboard() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<CourseDataStatusResponse | null>(null)
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    if (!token) return
    getCourseDataStatus({ token })
      .then(setData)
      .catch(() => setError(t('admin.notPartnerAdmin')))
  }, [token])

  const runCheck = () => {
    if (!token || checking) return
    setChecking(true)
    runCourseDataCheck({ token })
      .then(setData)
      .catch(() => { /* leave existing data; the check is best-effort */ })
      .finally(() => setChecking(false))
  }

  if (error) return <div className="text-red-600 mt-8 text-center">{error}</div>
  if (!data) return <div className="mt-8 text-center text-gray-500">{t('common.loading')}</div>

  const { statuses, coverage } = data

  // Freshness strip: each source → its status row + a current count + the local refresh command.
  const sources: { key: string; count: number | string; cmd: string }[] = [
    { key: 'epanduan_stpm', count: coverage.stpm_total, cmd: 'refresh_stpm' },
    { key: 'epanduan_spm', count: coverage.spm_total, cmd: 'sync_spm_mohe' },
    { key: 'uptvet', count: coverage.tvet_have, cmd: 'scrape_uptvet · audit_uptvet' },
    { key: 'emasco', count: coverage.emasco_total, cmd: 'load_masco_full' },
  ]

  const linkHealth = statuses['link_health']
  const audit = statuses['audit']
  const dash = '—'

  // Problem links: the failing URLs the last check recorded, grouped by reason for triage.
  const failures: LinkFailure[] = linkHealth?.summary?.failures ?? []
  const REASONS = ['gone', 'dns', 'timeout', 'conn', 'badurl']
  const groups = REASONS.map(k => ({ kind: k, items: failures.filter(f => f.kind === k) })).filter(g => g.items.length)
  const other = failures.filter(f => !REASONS.includes(f.kind))
  if (other.length) groups.push({ kind: 'other', items: other })

  const downloadCsv = () => {
    const rows = [['reason', 'url', 'http', 'institutions', 'rows'],
      ...failures.map(f => [f.kind, f.url, f.detail, f.institutions.join('; '), String(f.refs)])]
    const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    a.download = 'course-data-problem-links.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold mb-1">{t('admin.courseData.title')}</h1>
          <p className="text-sm text-gray-500">{t('admin.courseData.subtitle')}</p>
        </div>
        <div className="text-right shrink-0">
          <button
            onClick={runCheck}
            disabled={checking}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60 whitespace-nowrap"
          >
            {checking ? t('admin.courseData.checking') : t('admin.courseData.runCheck')}
          </button>
          <p className="text-[11px] text-gray-400 mt-1 max-w-[14rem]">{t('admin.courseData.runCheckHint')}</p>
        </div>
      </div>

      {/* Freshness strip */}
      <h2 className="font-semibold mb-3">{t('admin.courseData.freshness')}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {sources.map(({ key, count, cmd }) => {
          const s = statuses[key]
          const when = fmtDate(s?.last_run_at ?? null)
          return (
            <div key={key} className="bg-white rounded-lg p-5 shadow-sm border">
              <div className="flex items-center justify-between mb-2">
                <p className="font-medium text-gray-800">{t(`admin.courseData.src.${key}`)}</p>
                <span
                  className={`inline-block w-2.5 h-2.5 rounded-full ${when ? 'bg-green-500' : 'bg-gray-300'}`}
                  aria-hidden
                />
              </div>
              <p className="text-2xl font-bold text-blue-600">{count}</p>
              <p className="text-xs text-gray-400">{t('admin.courseData.courses')}</p>
              <p className="text-xs mt-2 text-gray-500">
                {when
                  ? `${t('admin.courseData.lastRun')}: ${when}`
                  : t('admin.courseData.notRunYet')}
              </p>
              <p className="text-[11px] mt-2 text-gray-400 font-mono break-words">
                {t('admin.courseData.refreshVia')}: {cmd}
              </p>
            </div>
          )
        })}
      </div>

      {/* Coverage + side cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg p-6 shadow-sm border lg:col-span-2">
          <h2 className="font-semibold mb-3">{t('admin.courseData.coverage')}</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-2 font-medium">{t('admin.courseData.source')}</th>
                <th className="py-2 font-medium text-right">{t('admin.courseData.have')}</th>
                <th className="py-2 font-medium text-right">{t('admin.courseData.available')}</th>
                <th className="py-2 font-medium text-right">{t('admin.courseData.gap')}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              <tr>
                <td className="py-2">{t('admin.courseData.src.epanduan_stpm')}</td>
                <td className="py-2 text-right">{coverage.stpm_active} / {coverage.stpm_total}</td>
                <td className="py-2 text-right text-gray-400">{dash}</td>
                <td className="py-2 text-right text-gray-400">{dash}</td>
              </tr>
              <tr>
                <td className="py-2">{t('admin.courseData.src.epanduan_spm')}</td>
                <td className="py-2 text-right">{coverage.spm_total}</td>
                <td className="py-2 text-right text-gray-400">{dash}</td>
                <td className="py-2 text-right text-gray-400">{dash}</td>
              </tr>
              <tr>
                <td className="py-2">{t('admin.courseData.src.uptvet')}</td>
                <td className="py-2 text-right">{coverage.tvet_have}</td>
                <td className="py-2 text-right">{coverage.uptvet_available ?? dash}</td>
                <td className={`py-2 text-right ${coverage.uptvet_gap ? 'text-amber-600 font-medium' : 'text-gray-400'}`}>
                  {coverage.uptvet_gap ?? dash}
                </td>
              </tr>
              <tr>
                <td className="py-2">{t('admin.courseData.src.emasco')}</td>
                <td className="py-2 text-right">{coverage.emasco_total}</td>
                <td className="py-2 text-right text-gray-400">{dash}</td>
                <td className="py-2 text-right text-gray-400">{dash}</td>
              </tr>
            </tbody>
          </table>
          {coverage.uptvet_available == null && (
            <p className="text-xs text-gray-400 mt-3">{t('admin.courseData.uptvetHint')}</p>
          )}
        </div>

        <div className="space-y-4">
          {/* Link health */}
          <div className="bg-white rounded-lg p-6 shadow-sm border">
            <h2 className="font-semibold mb-1">{t('admin.courseData.linkHealth')}</h2>
            {linkHealth ? (
              <>
                <p className="text-xs text-gray-400 mb-3">
                  {t('admin.courseData.lastRun')}: {fmtDate(linkHealth.last_run_at)}
                </p>
                <ul className="text-sm space-y-1">
                  <li className="flex justify-between"><span>{t('admin.courseData.alive')}</span><span className="text-green-600">{linkHealth.summary.alive ?? dash}</span></li>
                  <li className="flex justify-between"><span>{t('admin.courseData.dead')}</span><span className={Number(linkHealth.summary.dead) > 0 ? 'text-red-600 font-medium' : ''}>{linkHealth.summary.dead ?? dash}</span></li>
                  <li className="flex justify-between"><span>{t('admin.courseData.errors')}</span><span className="text-gray-500">{linkHealth.summary.errors ?? dash}</span></li>
                  {Number(linkHealth.summary.insecure) > 0 && (
                    <li className="flex justify-between text-gray-400"><span>{t('admin.courseData.insecure')}</span><span>{linkHealth.summary.insecure}</span></li>
                  )}
                </ul>
              </>
            ) : (
              <p className="text-sm text-gray-400">{t('admin.courseData.notRunYet')}</p>
            )}
            <p className="text-[11px] mt-3 text-gray-400 font-mono">{t('admin.courseData.refreshVia')}: validate_course_urls</p>
          </div>

          {/* Audit */}
          <div className="bg-white rounded-lg p-6 shadow-sm border">
            <h2 className="font-semibold mb-1">{t('admin.courseData.audit')}</h2>
            {audit ? (
              <p className="text-xs text-gray-400">{t('admin.courseData.lastRun')}: {fmtDate(audit.last_run_at)}</p>
            ) : (
              <p className="text-sm text-gray-400">{t('admin.courseData.notRunYet')}</p>
            )}
            <p className="text-[11px] mt-3 text-gray-400 font-mono">{t('admin.courseData.refreshVia')}: audit_data</p>
          </div>
        </div>
      </div>

      {/* Problem links — the failing URLs from the last check, grouped by reason */}
      {failures.length > 0 && (
        <div className="bg-white rounded-lg p-6 shadow-sm border mb-8">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-semibold">{t('admin.courseData.problemLinks')} ({failures.length})</h2>
            <button onClick={downloadCsv} className="text-sm text-blue-600 hover:underline">
              {t('admin.courseData.downloadCsv')}
            </button>
          </div>
          <p className="text-xs text-gray-400 mb-4">{t('admin.courseData.problemLinksHint')}</p>
          <div className="space-y-3">
            {groups.map(g => (
              <details key={g.kind} className="border rounded-lg" open={g.kind === 'gone'}>
                <summary className="cursor-pointer px-4 py-2 text-sm font-medium flex justify-between items-center">
                  <span>{t(`admin.courseData.reason.${g.kind}`)}</span>
                  <span className="text-gray-500">{g.items.length}</span>
                </summary>
                <ul className="divide-y border-t">
                  {g.items.map((f, i) => (
                    <li key={i} className="px-4 py-2">
                      <p className="text-sm text-gray-800">
                        {f.institutions.join(', ') || dash}
                        {f.refs > 1 && <span className="text-gray-400"> · {f.refs} {t('admin.courseData.rows')}</span>}
                      </p>
                      <a href={f.url.startsWith('http') ? f.url : `https://${f.url}`}
                         target="_blank" rel="noopener noreferrer"
                         className="text-xs text-blue-600 hover:underline break-all">
                        {f.url}{f.detail ? ` (${f.detail})` : ''}
                      </a>
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-gray-400">{t('admin.courseData.readOnlyNote')}</p>
    </div>
  )
}
