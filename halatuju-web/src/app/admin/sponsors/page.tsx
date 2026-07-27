'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { seenBand } from '@/lib/sponsorDetail'
import { listSponsors, reviewSponsor, type AdminSponsor } from '@/lib/admin-api'

// The ORGANISATION column was dropped on 2026-07-27: empty on all nine prod rows, and it cost
// a quarter of the table's width. Its space pays for GIVEN + LAST SEEN — what an admin
// actually scans a funder list for. `given` is org-fenced server-side (a tenant sees its own
// share); `last_seen_at` had no home at all before this sprint.
const seenTone: Record<string, string> = {
  never: 'text-amber-700 font-semibold',
  dormant: 'text-amber-700',
  recent: 'text-gray-500',
  today: 'text-gray-500',
}

const statusBadge = (s: string) =>
  s === 'approved' ? 'bg-green-100 text-green-700'
    : s === 'pending' ? 'bg-amber-100 text-amber-700'
      : s === 'suspended' ? 'bg-orange-100 text-orange-700'
        : 'bg-red-100 text-red-600'

const STATUS_OPTIONS = ['pending', 'approved', 'rejected', 'suspended']

// Which review actions to offer for a sponsor in a given status.
const actionsFor = (status: string): Array<'approve' | 'reject' | 'suspend'> =>
  status === 'pending' ? ['approve', 'reject']
    : status === 'approved' ? ['suspend']
      : ['approve'] // rejected / suspended → reconsider

const actionStyle: Record<string, string> = {
  approve: 'bg-green-600 hover:bg-green-700',
  reject: 'bg-red-600 hover:bg-red-700',
  suspend: 'bg-orange-600 hover:bg-orange-700',
}

export default function AdminSponsorsList() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [sponsors, setSponsors] = useState<AdminSponsor[]>([])
  const [statusF, setStatusF] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    listSponsors(statusF || undefined, { token })
      .then((d) => setSponsors(d.sponsors))
      .catch(() => setError(t('admin.sponsors.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, statusF])

  useEffect(() => { load() }, [load])

  const handleReview = async (id: number, action: 'approve' | 'reject' | 'suspend') => {
    if (!token) return
    setBusyId(id)
    setError('')
    try {
      const updated = await reviewSponsor(id, action, { token })
      setSponsors((prev) => prev.map((s) => (s.id === id ? updated : s)))
    } catch {
      setError(t('admin.sponsors.actionFailed'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">{t('admin.sponsors.title')}</h1>
      <p className="text-sm text-gray-500 mt-1 mb-4">{t('admin.sponsors.desc')}</p>

      <div className="flex flex-wrap gap-3 mb-4">
        <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.sponsors.allStatuses')}</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {error && <div className="text-red-600 mb-3">{error}</div>}
      {loading ? (
        <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>
      ) : sponsors.length === 0 ? (
        <div className="text-center text-gray-500 mt-8">{t('admin.sponsors.empty')}</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50/80 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.sponsors.name')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.sponsors.status')}</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.sponsors.colGiven')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.sponsors.colLastSeen')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.sponsors.registered')}</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.sponsors.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sponsors.map((s) => (
                <tr key={s.id} className="hover:bg-blue-50/40 transition-colors align-top">
                  <td className="px-4 py-3 border-l-[3px] border-l-blue-500">
                    {/* The name opens the whole record — everything the flat table could not show. */}
                    <Link href={`/admin/sponsors/${s.id}`} className="font-medium text-blue-600 hover:text-blue-800">
                      {s.name || '—'}
                    </Link>
                    <div className="text-xs text-gray-500 mt-0.5">{s.email || '—'}</div>
                    {s.note && <div className="text-xs text-gray-500 mt-0.5 max-w-xs whitespace-pre-wrap">{s.note}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusBadge(s.status)}`}>{s.status}</span>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                    {Number(s.given) > 0 ? Number(s.given).toLocaleString('en-MY', { minimumFractionDigits: 2 }) : '—'}
                  </td>
                  <td className={`px-4 py-3 text-sm ${seenTone[seenBand(s.last_seen_at)]}`}>
                    {s.last_seen_at
                      ? t(`admin.sponsors.seen.${seenBand(s.last_seen_at)}`, { date: formatDate(s.last_seen_at) })
                      : t('admin.sponsors.seen.never')}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(s.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      {actionsFor(s.status).map((a) => (
                        <button
                          key={a}
                          onClick={() => handleReview(s.id, a)}
                          disabled={busyId === s.id}
                          className={`text-white text-xs font-semibold px-3 py-1.5 rounded-lg disabled:opacity-50 ${actionStyle[a]}`}
                        >
                          {t(`admin.sponsors.action.${a}`)}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
