'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import Link from 'next/link'
import { searchCourses, type SearchCourse, type SearchFilters, type EligibleCourse } from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import CourseCard from '@/components/CourseCard'
import { useT } from '@/lib/i18n'

const PAGE_SIZE = 6

export default function SearchPage() {
  const { t } = useT()
  const [courses, setCourses] = useState<SearchCourse[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [filters, setFilters] = useState<SearchFilters | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Filter state
  const [query, setQuery] = useState('')
  const [level, setLevel] = useState('')
  const [field, setField] = useState('')
  const [sourceType, setSourceType] = useState('')
  const [state, setState] = useState('')
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

  // Debounced search query
  const [debouncedQuery, setDebouncedQuery] = useState('')
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

        {/* Search bar */}
        <div className="relative mb-4">
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
            className="input w-full pl-10"
            placeholder={t('search.searchPlaceholder')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {/* Filter row */}
        <div className="flex flex-wrap gap-2 mb-6">
          <select
            className="input w-auto"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
          >
            <option value="">{t('search.allTypes')}</option>
            {filters?.source_types.map((st) => (
              <option key={st} value={st}>
                {SOURCE_LABELS[st] || st}
              </option>
            ))}
          </select>

          <select
            className="input w-auto"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
          >
            <option value="">{t('search.allLevels')}</option>
            {filters?.levels.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>

          <select
            className="input w-auto"
            value={state}
            onChange={(e) => setState(e.target.value)}
          >
            <option value="">{t('search.allStates')}</option>
            {filters?.states.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select
            className="input w-auto"
            value={field}
            onChange={(e) => setField(e.target.value)}
          >
            <option value="">{t('search.allFields')}</option>
            {filters?.fields.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>

        {/* Results meta */}
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-gray-600">
            {t('search.showing')}{' '}
            <span className="font-medium">{Math.min(displayCount, displayedCourses.length)}</span>
            {' '}{t('search.of')}{' '}
            <span className="font-medium">{displayedCourses.length}</span>
            {' '}{t('search.courses')}
          </p>

          {eligibleIds && (
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={eligibleOnly}
                onChange={(e) => setEligibleOnly(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              {t('search.eligibleOnly')}
            </label>
          )}
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
                <div key={course.course_id} className="relative">
                  <CourseCard
                    course={toEligible(course)}
                    isSaved={false}
                  />
                  {course.institution_count > 0 && (
                    <div className="absolute bottom-3 right-3 px-2 py-0.5 bg-gray-100 text-gray-500 text-xs rounded-full">
                      {course.institution_count} {t('search.institutions')}
                    </div>
                  )}
                </div>
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
