'use client'

import { Suspense, useState, useEffect, useCallback, useMemo } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { searchCourses, type SearchCourse, type SearchFilters, type EligibleCourse } from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import CourseCard from '@/components/CourseCard'
import FilterPill from '@/components/FilterPill'
import clsx from 'clsx'
import { useT } from '@/lib/i18n'

const PAGE_SIZE = 6

export default function SearchPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-gray-50">
        <AppHeader />
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
        </div>
        <AppFooter />
      </main>
    }>
      <SearchPageInner />
    </Suspense>
  )
}

function SearchPageInner() {
  const { t } = useT()
  const searchParams = useSearchParams()
  const router = useRouter()
  const [courses, setCourses] = useState<SearchCourse[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [filters, setFilters] = useState<SearchFilters | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Initialise filter state from URL search params
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [level, setLevel] = useState(searchParams.get('level') || '')
  const [field, setField] = useState(searchParams.get('field') || '')
  const [sourceType, setSourceType] = useState(searchParams.get('type') || '')
  const [state, setState] = useState(searchParams.get('state') || '')
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)

  // Eligible toggle
  const [eligibleOnly, setEligibleOnly] = useState(false)
  const [eligibleIds, setEligibleIds] = useState<Set<string> | null>(null)

  // Load eligible course IDs from localStorage (if available)
  useEffect(() => {
    try {
      const stored = localStorage.getItem('halatuju_eligible_courses')
      if (stored) {
        const ids: string[] = JSON.parse(stored)
        setEligibleIds(new Set(ids))
      }
    } catch {
      // No eligible data available
    }
  }, [])

  // Sync filter state to URL search params (replace, not push, to avoid history spam)
  useEffect(() => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (level) params.set('level', level)
    if (field) params.set('field', field)
    if (sourceType) params.set('type', sourceType)
    if (state) params.set('state', state)
    const qs = params.toString()
    router.replace(qs ? `/search?${qs}` : '/search', { scroll: false })
  }, [query, level, field, sourceType, state, router])

  // Debounced search query
  const [debouncedQuery, setDebouncedQuery] = useState(query)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  // Fetch courses when filters change
  const fetchCourses = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await searchCourses({
        q: debouncedQuery || undefined,
        level: level || undefined,
        field: field || undefined,
        source_type: sourceType || undefined,
        state: state || undefined,
        limit: 200,
      })
      setCourses(data.courses)
      setTotalCount(data.total_count)
      if (!filters) {
        setFilters(data.filters)
      }
    } catch {
      setCourses([])
      setTotalCount(0)
    } finally {
      setIsLoading(false)
    }
  }, [debouncedQuery, level, field, sourceType, state, filters])

  useEffect(() => {
    fetchCourses()
  }, [fetchCourses])

  // Reset display count when filters change
  useEffect(() => {
    setDisplayCount(PAGE_SIZE)
  }, [debouncedQuery, level, field, sourceType, state, eligibleOnly])

  // Apply eligible filter client-side
  const displayedCourses = useMemo(() => {
    let result = courses
    if (eligibleOnly && eligibleIds) {
      result = result.filter(c => eligibleIds.has(c.course_id))
    }
    return result
  }, [courses, eligibleOnly, eligibleIds])

  const visibleCourses = displayedCourses.slice(0, displayCount)
  const remaining = displayedCourses.length - displayCount

  // Map SearchCourse to EligibleCourse for CourseCard compatibility
  const toEligible = (c: SearchCourse): EligibleCourse => ({
    course_id: c.course_id,
    course_name: c.course_name,
    level: c.level,
    field: c.field,
    source_type: c.source_type,
    merit_cutoff: c.merit_cutoff,
    student_merit: null,
    merit_label: null,
    merit_color: null,
  })

  const hasActiveFilters = !!(query || level || field || sourceType || state)

  const clearAllFilters = () => {
    setQuery('')
    setLevel('')
    setField('')
    setSourceType('')
    setState('')
    setEligibleOnly(false)
  }

  // Source type labels for filter dropdown
  const SOURCE_LABELS: Record<string, string> = {
    poly: t('dashboard.polytechnic'),
    kkom: t('dashboard.kolej'),
    tvet: t('dashboard.tvet'),
    ua: t('dashboard.university'),
    pismp: t('dashboard.teacherTraining'),
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-1">
            {t('search.title')}
          </h1>
          <p className="text-gray-600 text-sm">
            {t('search.subtitle')}
          </p>
        </div>

        {/* Search + Filter container */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 mb-4">
          {/* Search bar */}
          <div className="relative mb-3">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              className="w-full pl-10 px-4 py-3 rounded-lg border border-gray-200 bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent placeholder:text-gray-400"
              placeholder={t('search.searchPlaceholder')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {/* Filter row */}
          <div className="flex flex-wrap items-center gap-2">
          <FilterPill
            label={t('search.allTypes')}
            value={sourceType}
            options={filters?.source_types ?? []}
            optionLabels={SOURCE_LABELS}
            onChange={setSourceType}
          />

          <FilterPill
            label={t('search.allLevels')}
            value={level}
            options={filters?.levels ?? []}
            onChange={setLevel}
          />

          <FilterPill
            label={t('search.allStates')}
            value={state}
            options={filters?.states ?? []}
            onChange={setState}
          />

          <FilterPill
            label={t('search.allFields')}
            value={field}
            options={filters?.fields ?? []}
            onChange={setField}
          />

          {/* Clear Filters — always visible and blue */}
          <button
            onClick={clearAllFilters}
            disabled={!hasActiveFilters}
            className="px-3 py-1.5 text-sm font-medium text-primary-500 hover:text-primary-700 hover:bg-primary-50 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-default"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            {t('search.clearFilters')}
          </button>

          {/* Spacer — pushes eligibility toggle right on desktop */}
          <div className="flex-1 min-w-0" />

          {/* Eligibility toggle — always visible, disabled when no match data */}
          <label className={clsx(
            'flex items-center gap-2 flex-shrink-0',
            eligibleIds ? 'cursor-pointer' : 'cursor-default opacity-60'
          )}>
            <div className="relative inline-flex items-center">
              <input
                type="checkbox"
                checked={eligibleOnly}
                onChange={(e) => eligibleIds && setEligibleOnly(e.target.checked)}
                disabled={!eligibleIds}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-gray-200 rounded-full peer-checked:bg-primary-500 transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow-sm transition-transform peer-checked:translate-x-5" />
            </div>
            <div className="text-sm">
              <span className="font-medium text-gray-700">{t('search.eligibleOnly')}</span>
              <span className="block text-xs text-gray-400">{t('search.eligibleToggleDesc')}</span>
            </div>
          </label>
          </div>
        </div>

        {/* Results meta */}
        <div className="mb-4">
          <p className="text-sm text-gray-600">
            {t('search.showing')}{' '}
            <span className="font-medium">{Math.min(displayCount, displayedCourses.length)}</span>
            {' '}{t('search.of')}{' '}
            <span className="font-medium">{displayedCourses.length}</span>
            {' '}{t('search.courses')}
          </p>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
            <p className="text-gray-600">{t('common.loading')}</p>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && displayedCourses.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-2">{t('search.noCourses')}</p>
            <p className="text-gray-400 text-sm">{t('search.tryDifferent')}</p>
          </div>
        )}

        {/* Results grid */}
        {!isLoading && visibleCourses.length > 0 && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {visibleCourses.map((course) => (
                <CourseCard
                  key={course.course_id}
                  course={toEligible(course)}
                  isSaved={false}
                  institutionName={course.institution_name}
                  institutionState={course.institution_state}
                  institutionCount={course.institution_count}
                />
              ))}
            </div>

            {remaining > 0 && (
              <div className="text-center py-4">
                <button
                  className="btn-secondary"
                  onClick={() => setDisplayCount(displayCount + PAGE_SIZE)}
                >
                  {t('search.loadMore')} ({remaining} {t('search.remaining')})
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <AppFooter />
    </main>
  )
}
