'use client'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { getCourseDataStatus, type CourseDataStatusResponse } from '@/lib/admin-api'
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

  useEffect(() => {
    if (!token) return
    getCourseDataStatus({ token })
      .then(setData)
      .catch(() => setError(t('admin.notPartnerAdmin')))
  }, [token])

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

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">{t('admin.courseData.title')}</h1>
      <p className="text-sm text-gray-500 mb-6">{t('admin.courseData.subtitle')}</p>

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

      <p className="text-xs text-gray-400">{t('admin.courseData.readOnlyNote')}</p>
    </div>
  )
}
