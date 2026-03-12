'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import {
  searchStpmProgrammes,
  type StpmEligibleProgramme,
  type StpmSearchFilters,
} from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

const ITEMS_PER_PAGE = 24

function StpmSearchContent() {
  const { t } = useT()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [programmes, setProgrammes] = useState<StpmEligibleProgramme[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [filters, setFilters] = useState<StpmSearchFilters>({ universities: [], streams: [] })
  const [isLoading, setIsLoading] = useState(true)
  const [displayCount, setDisplayCount] = useState(ITEMS_PER_PAGE)

  const query = searchParams.get('q') || ''
  const university = searchParams.get('university') || ''
  const stream = searchParams.get('stream') || ''

  const updateParam = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    router.replace(`/stpm/search?${params.toString()}`)
  }, [router, searchParams])

  const [searchInput, setSearchInput] = useState(query)
  useEffect(() => {
    const timer = setTimeout(() => {
      updateParam('q', searchInput)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput, updateParam])

  useEffect(() => {
    setIsLoading(true)
    setDisplayCount(ITEMS_PER_PAGE)
    searchStpmProgrammes({
      q: query || undefined,
      university: university || undefined,
      stream: stream || undefined,
      limit: 200,
    }).then(data => {
      setProgrammes(data.programmes)
      setTotalCount(data.total_count)
      setFilters(data.filters)
    }).catch(err => {
      console.error('STPM search failed:', err)
    }).finally(() => {
      setIsLoading(false)
    })
  }, [query, university, stream])

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader />
      <div className="container mx-auto px-6 py-8 flex-1">
        <div className="mb-6">
          <Link href="/dashboard" className="text-sm text-gray-500 hover:text-primary-500">
            &larr; {t('stpm.backToDashboard')}
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-2">{t('stpm.searchTitle')}</h1>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-3">
            <input
              type="text"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder={t('stpm.searchPlaceholder')}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <select
              value={university}
              onChange={e => updateParam('university', e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm bg-white"
            >
              <option value="">{t('stpm.allUniversities')}</option>
              {filters.universities.map(u => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
            <select
              value={stream}
              onChange={e => updateParam('stream', e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm bg-white"
            >
              <option value="">{t('stpm.allStreams')}</option>
              {filters.streams.map(s => (
                <option key={s} value={s}>{t(`stpm.${s}`)}</option>
              ))}
            </select>
          </div>
        </div>

        <p className="text-sm text-gray-500 mb-4">
          {totalCount} {t('stpm.programmesFound')}
        </p>

        {isLoading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
          </div>
        ) : programmes.length === 0 ? (
          <div className="text-center py-12">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">{t('stpm.noResults')}</h2>
            <p className="text-gray-500">{t('stpm.noResultsDesc')}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {programmes.slice(0, displayCount).map(prog => (
                <Link
                  key={prog.program_id}
                  href={`/stpm/${prog.program_id}`}
                  className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-5 block"
                >
                  <h3 className="font-semibold text-gray-900 text-sm mb-2 line-clamp-2">
                    {prog.program_name}
                  </h3>
                  <p className="text-xs text-gray-500 mb-3">{prog.university}</p>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full">
                      CGPA &ge; {prog.min_cgpa.toFixed(2)}
                    </span>
                    <span className="px-2 py-0.5 bg-green-50 text-green-700 text-xs rounded-full">
                      MUET &ge; Band {prog.min_muet_band}
                    </span>
                    {prog.req_interview && (
                      <span className="px-2 py-0.5 bg-amber-50 text-amber-700 text-xs rounded-full">
                        Interview
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
            {programmes.length > displayCount && (
              <button
                onClick={() => setDisplayCount(prev => prev + ITEMS_PER_PAGE)}
                className="mt-4 w-full py-3 text-primary-600 hover:text-primary-700 text-sm font-medium"
              >
                {t('stpm.loadMore')} ({programmes.length - displayCount} {t('stpm.remaining')})
              </button>
            )}
          </>
        )}
      </div>
      <AppFooter />
    </div>
  )
}

export default function StpmSearchPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
      <StpmSearchContent />
    </Suspense>
  )
}
