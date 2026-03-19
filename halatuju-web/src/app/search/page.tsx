'use client'

import { Suspense, useState, useEffect, useCallback, useMemo } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { searchCourses, checkEligibility, checkStpmEligibility, type SearchCourse, type SearchFilters, type EligibleCourse, type StudentProfile } from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import CourseCard from '@/components/CourseCard'
import FilterPill from '@/components/FilterPill'
import { useAuth } from '@/lib/auth-context'
import { useSavedCourses } from '@/hooks/useSavedCourses'
import { useFieldTaxonomy } from '@/hooks/useFieldTaxonomy'
import clsx from 'clsx'
import { useT } from '@/lib/i18n'
import { KEY_PROFILE, KEY_GRADES, KEY_EXAM_TYPE, KEY_STPM_GRADES, KEY_STPM_CGPA, KEY_MUET_BAND, KEY_SPM_PREREQ, KEY_RESUME_ACTION, hasGrades } from '@/lib/storage'

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
  const { t, locale } = useT()
  const searchParams = useSearchParams()
  const router = useRouter()
  const { isAuthenticated, showAuthGate } = useAuth()
  const { savedIds, toggleSave } = useSavedCourses()
  const { fieldOptions, loaded: taxonomyLoaded } = useFieldTaxonomy(locale)
  const [courses, setCourses] = useState<SearchCourse[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [filters, setFilters] = useState<SearchFilters | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Initialise filter state from URL search params
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [level, setLevel] = useState(searchParams.get('level') || '')
  const [field, setField] = useState(searchParams.get('field_key') || searchParams.get('field') || '')
  const [sourceType, setSourceType] = useState(searchParams.get('type') || '')
  const [state, setState] = useState(searchParams.get('state') || '')
  const [qualification, setQualification] = useState(searchParams.get('qualification') || '')
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)

  // Eligible toggle
  const [eligibleOnly, setEligibleOnly] = useState(false)
  const [eligibleIds, setEligibleIds] = useState<Set<string> | null>(null)
  const [eligibleMap, setEligibleMap] = useState<Map<string, EligibleCourse> | null>(null)
  const [eligibleLoading, setEligibleLoading] = useState(false)

  // Fetch eligible course data from the API (SPM + STPM)
  const fetchEligibleIds = useCallback(async () => {
    try {
      setEligibleLoading(true)
      const allIds = new Set<string>()
      const allMap = new Map<string, EligibleCourse>()

      // SPM eligibility — merge grades (stored separately) into profile
      const stored = localStorage.getItem(KEY_PROFILE)
      const gradesStr = localStorage.getItem(KEY_GRADES)
      if (stored && gradesStr) {
        const parsedProfile = JSON.parse(stored)
        const parsedGrades = JSON.parse(gradesStr)
        const profile: StudentProfile = { ...parsedProfile, grades: parsedGrades }
        if (Object.keys(profile.grades).length > 0) {
          const data = await checkEligibility(profile)
          for (const c of data.eligible_courses) {
            allIds.add(c.course_id)
            allMap.set(c.course_id, c)
          }
        }
      }

      // STPM eligibility — check if STPM grades exist
      const examType = localStorage.getItem(KEY_EXAM_TYPE)
      const stpmGradesStr = localStorage.getItem(KEY_STPM_GRADES)
      const stpmCgpaStr = localStorage.getItem(KEY_STPM_CGPA)
      const muetBandStr = localStorage.getItem(KEY_MUET_BAND)
      const spmPrereqStr = localStorage.getItem(KEY_SPM_PREREQ)

      if (examType === 'stpm' && stpmGradesStr && stpmCgpaStr && muetBandStr) {
        const profileData = stored ? JSON.parse(stored) : {}
        const genderMap: Record<string, string> = { male: 'Lelaki', female: 'Perempuan' }
        const nationalityMap: Record<string, string> = { malaysian: 'Warganegara', non_malaysian: 'Bukan Warganegara' }

        const stpmData = await checkStpmEligibility({
          stpm_grades: JSON.parse(stpmGradesStr),
          spm_grades: spmPrereqStr ? JSON.parse(spmPrereqStr) : {},
          cgpa: parseFloat(stpmCgpaStr),
          muet_band: parseInt(muetBandStr),
          gender: genderMap[profileData.gender] || '',
          nationality: nationalityMap[profileData.nationality] || 'Warganegara',
          colorblind: !!profileData.colorblind,
        })

        // Map STPM eligible courses to EligibleCourse format
        for (const prog of stpmData.eligible_courses) {
          allIds.add(prog.course_id)
          allMap.set(prog.course_id, {
            course_id: prog.course_id,
            course_name: prog.course_name,
            level: 'Ijazah Sarjana Muda',
            field: '',
            field_key: prog.field_key || '',
            source_type: 'ua',
            merit_cutoff: prog.merit_score,
            student_merit: null,
            merit_label: null,
            merit_color: null,
          })
        }
      }

      setEligibleIds(allIds)
      setEligibleMap(allMap)
    } catch {
      // Eligibility check failed — toggle stays off
    } finally {
      setEligibleLoading(false)
    }
  }, [])

  // Handle toggle click
  const handleEligibleToggle = useCallback(() => {
    if (eligibleOnly) {
      // Turning off — always allowed
      setEligibleOnly(false)
      return
    }
    if (!isAuthenticated) {
      if (!hasGrades()) {
        router.push('/onboarding/exam-type')
        return
      }
      showAuthGate('eligible')
      return
    }
    if (eligibleIds) {
      // Already fetched — just turn on
      setEligibleOnly(true)
    } else {
      // Fetch then turn on
      fetchEligibleIds().then(() => setEligibleOnly(true))
    }
  }, [eligibleOnly, isAuthenticated, eligibleIds, showAuthGate, fetchEligibleIds])

  // Auto-activate toggle after login (user was trying to enable it)
  useEffect(() => {
    if (isAuthenticated && !eligibleOnly && !eligibleIds) {
      // Check if user just came from auth gate for eligible reason
      const resume = localStorage.getItem(KEY_RESUME_ACTION)
      if (resume) {
        try {
          const { action } = JSON.parse(resume)
          if (action === 'eligible') {
            localStorage.removeItem(KEY_RESUME_ACTION)
            fetchEligibleIds().then(() => setEligibleOnly(true))
          }
        } catch {
          // ignore
        }
      }
    }
  }, [isAuthenticated, eligibleOnly, eligibleIds, fetchEligibleIds])

  // Sync filter state to URL search params (replace, not push, to avoid history spam)
  useEffect(() => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (level) params.set('level', level)
    if (field) params.set('field_key', field)
    if (sourceType) params.set('type', sourceType)
    if (state) params.set('state', state)
    if (qualification) params.set('qualification', qualification)
    const qs = params.toString()
    router.replace(qs ? `/search?${qs}` : '/search', { scroll: false })
  }, [query, level, field, sourceType, state, qualification, router])

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
        field_key: field || undefined,
        source_type: sourceType || undefined,
        state: state || undefined,
        qualification: qualification || undefined,
        limit: 10000,
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
  }, [debouncedQuery, level, field, sourceType, state, qualification, filters])

  useEffect(() => {
    fetchCourses()
  }, [fetchCourses])

  // Reset display count when filters change
  useEffect(() => {
    setDisplayCount(PAGE_SIZE)
  }, [debouncedQuery, level, field, sourceType, state, qualification, eligibleOnly])

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
  const toEligible = (c: SearchCourse): EligibleCourse => {
    const match = eligibleMap?.get(c.course_id)
    return {
      course_id: c.course_id,
      course_name: c.course_name,
      level: c.level,
      field: c.field,
      field_key: c.field_key,
      source_type: c.source_type,
      pathway_type: c.pathway_type,
      qualification: c.qualification,
      merit_cutoff: c.merit_cutoff,
      student_merit: match?.student_merit ?? null,
      merit_label: match?.merit_label ?? null,
      merit_color: match?.merit_color ?? null,
    }
  }

  const hasActiveFilters = !!(query || level || field || sourceType || state || qualification)

  const clearAllFilters = () => {
    setQuery('')
    setLevel('')
    setField('')
    setSourceType('')
    setState('')
    setQualification('')
    setEligibleOnly(false)
  }

  // Source type labels for filter dropdown
  const SOURCE_LABELS: Record<string, string> = {
    ua: 'Universiti',
    pismp: 'IPGM',
    poly: 'Politeknik',
    iljtm: 'ILJTM',
    ilkbs: 'ILKBS',
    kkom: 'Kolej Komuniti',
    matric: 'Kolej Matrikulasi',
    stpm: 'Tingkatan 6',
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
          {/* Qualification filter — toggle buttons */}
          <div className="flex rounded-lg border border-gray-200 overflow-hidden">
            <button
              onClick={() => setQualification(qualification === 'SPM' ? '' : 'SPM')}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                qualification === 'SPM'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              SPM
            </button>
            <button
              onClick={() => setQualification(qualification === 'STPM' ? '' : 'STPM')}
              className={`px-3 py-1.5 text-sm font-medium transition-colors border-l border-gray-200 ${
                qualification === 'STPM'
                  ? 'bg-purple-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              STPM
            </button>
          </div>

          <FilterPill
            label={t('search.allTypes')}
            value={sourceType}
            options={(filters?.source_types ?? []).filter(t => t !== 'tvet').sort((a, b) =>
              (SOURCE_LABELS[a] ?? a).localeCompare(SOURCE_LABELS[b] ?? b, 'ms')
            )}
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
            options={taxonomyLoaded ? [...fieldOptions].sort((a, b) => a.label.localeCompare(b.label, 'ms')).map(f => f.key) : (filters?.fields ?? [])}
            optionLabels={taxonomyLoaded ? Object.fromEntries(fieldOptions.map(f => [f.key, f.label])) : undefined}
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

          {/* Eligibility toggle — prompts login if not authenticated */}
          <button
            type="button"
            onClick={handleEligibleToggle}
            disabled={eligibleLoading}
            className="flex items-center gap-2 flex-shrink-0 cursor-pointer disabled:opacity-60"
          >
            <div className="relative inline-flex items-center">
              <div className={clsx(
                'w-10 h-5 rounded-full transition-colors',
                eligibleOnly ? 'bg-primary-500' : 'bg-gray-200'
              )} />
              <div className={clsx(
                'absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow-sm transition-transform',
                eligibleOnly && 'translate-x-5'
              )} />
            </div>
            <div className="text-sm text-left">
              <span className="font-medium text-gray-700">{t('search.eligibleOnly')}</span>
              <span className="block text-xs text-gray-400">{t('search.eligibleToggleDesc')}</span>
            </div>
          </button>
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
                  isSaved={savedIds.has(course.course_id)}
                  onToggleSave={toggleSave}
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
                  onClick={() => {
                    if (!isAuthenticated) { showAuthGate('loadmore'); return }
                    setDisplayCount(displayCount + PAGE_SIZE)
                  }}
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
