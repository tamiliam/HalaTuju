'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { filterPool, poolFacets } from '@/lib/sponsorFilter'

/**
 * Students — the anonymised marketplace. Browse + filter the pool (client-side over the
 * already-fetched cards) and open a student. Funding is confirmed with the owner as a
 * fast follow (the detail page carries the "Support" affordance).
 */
export default function StudentsPage() {
  const { t } = useT()
  const { pool } = useSponsorPortal()

  const [field, setField] = useState('')
  const [state, setState] = useState('')
  const [level, setLevel] = useState('')

  const rows = pool || []
  const facets = useMemo(() => poolFacets(rows), [rows])
  const shown = useMemo(() => filterPool(rows, { field, state, level }), [rows, field, state, level])

  const selectCls = 'text-sm border border-gray-200 rounded-xl px-3 py-2 bg-white'

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">{t('sponsorPortal.students.title')}</h1>
      <p className="text-sm text-gray-600 mt-1 max-w-2xl">{t('sponsorPortal.students.intro')}</p>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mt-5">
        <select value={field} onChange={(e) => setField(e.target.value)} className={selectCls}>
          <option value="">{t('sponsorPortal.students.allFields')}</option>
          {facets.fields.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
        <select value={state} onChange={(e) => setState(e.target.value)} className={selectCls}>
          <option value="">{t('sponsorPortal.students.allStates')}</option>
          {facets.states.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={level} onChange={(e) => setLevel(e.target.value)} className={selectCls}>
          <option value="">{t('sponsorPortal.students.allLevels')}</option>
          {facets.levels.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        <span className="ml-auto self-center text-xs text-gray-400">
          {t('sponsorPortal.students.shown').replace('{count}', String(shown.length))}
        </span>
      </div>

      {/* Anonymity note */}
      <div className="mt-4 rounded-lg bg-blue-50 border border-blue-100 px-4 py-2.5 text-xs text-blue-800">
        {t('sponsorPool.anonymityNote')}
      </div>

      {/* Grid / empty states */}
      {pool === null ? (
        <p className="text-center text-gray-500 mt-12">{t('common.loading')}</p>
      ) : rows.length === 0 ? (
        <div className="text-center text-gray-500 mt-8 rounded-xl bg-white border border-dashed px-6 py-10">
          {t('sponsorPool.empty')}
        </div>
      ) : shown.length === 0 ? (
        <div className="text-center text-gray-500 mt-8 rounded-xl bg-white border border-dashed px-6 py-10">
          {t('sponsorPortal.students.filteredEmpty')}
        </div>
      ) : (
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((s) => (
            <Link key={s.id} href={`/sponsor/students/${s.id}`}
              className="block bg-white rounded-2xl border p-4 hover:border-blue-300 hover:shadow-sm transition">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-gray-900">{s.ref}</span>
                {s.state && <span className="text-xs text-gray-500">{s.state}</span>}
              </div>
              <p className="text-[15px] font-medium text-gray-800 mt-1">{s.field || '—'}</p>
              {s.academic && <p className="text-xs text-gray-500">{s.academic}</p>}
              {s.funding_categories.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {s.funding_categories.map((c) => (
                    <span key={c} className="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{c}</span>
                  ))}
                </div>
              )}
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-50">
                {s.award_amount ? <span className="text-sm font-semibold text-gray-900">RM {s.award_amount}</span> : <span />}
                <span className="text-xs text-blue-600 font-medium">{t('sponsorPortal.students.support')} →</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
