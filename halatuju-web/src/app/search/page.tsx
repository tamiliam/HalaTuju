'use client'

import { Suspense, useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { searchCourses, type SearchCourse, type SearchFilters, type EligibleCourse } from '@/lib/api'
import { loadEligibleCourses } from '@/lib/searchEligibility'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import CourseCard from '@/components/CourseCard'
import FilterPill from '@/components/FilterPill'
import SearchFilterSheet, { type FacetGroup } from '@/components/search/SearchFilterSheet'
import { useAuth } from '@/lib/auth-context'
// Mobile M3: the phone filter sheet's words (the `discovery` slice), loaded by this PAGE.
import '@/lib/messagesDiscovery'
import { useSavedCourses } from '@/hooks/useSavedCourses'
import { useFieldTaxonomy } from '@/hooks/useFieldTaxonomy'
import clsx from 'clsx'
import { useT } from '@/lib/i18n'
import { isThirdRoute } from '@/lib/qualification'
import { isBumiputera } from '@/lib/bumiputera'
import { KEY_PROFILE, KEY_EXAM_TYPE, KEY_RESUME_ACTION, hasGrades, COURSE_PAGE_SIZE } from '@/lib/storage'
import { PHONE_GUTTER, PHONE_SECTION } from '@/lib/phoneSection'   // rule 15 (Mobile M4b)

export default function SearchPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-ground-50">
        <AppHeader />
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-brand-shape border-t-transparent" />
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
  const { isAuthenticated, showAuthGate, profile: authProfile } = useAuth()
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
  const [aliran, setAliran] = useState(searchParams.get('aliran') || '')
  const [displayCount, setDisplayCount] = useState(COURSE_PAGE_SIZE)
  // Mobile M3: the phone filter sheet (below `md`; the desktop keeps its row of pills).
  const [filtersOpen, setFiltersOpen] = useState(false)
  // Matriculation / Asasi / Diploma results held in this browser (third results route S2b)?
  const [thirdRoute, setThirdRoute] = useState(false)
  // The server's results_held when a profile is loaded (S2b review), else this browser's own.
  // Bumi coverage Sprint B: a Malaysian who said yes also sees Bumiputera-only courses. Read from
  // this browser's profile (AuthProvider writes the server's answer into it on every hydrate).
  const [bumi, setBumi] = useState(false)
  useEffect(() => {
    setThirdRoute(isThirdRoute(authProfile?.results_held || localStorage.getItem(KEY_EXAM_TYPE)))
    let demo: Record<string, unknown> = {}
    try { demo = JSON.parse(localStorage.getItem(KEY_PROFILE) || '{}') } catch { /* malformed — no */ }
    setBumi(isBumiputera(demo as { nationality?: string; bumiputera?: boolean | null }))
  }, [authProfile])

  // Eligible toggle
  const [eligibleOnly, setEligibleOnly] = useState(false)
  const [eligibleIds, setEligibleIds] = useState<Set<string> | null>(null)
  const [eligibleMap, setEligibleMap] = useState<Map<string, EligibleCourse> | null>(null)
  const [eligibleLoading, setEligibleLoading] = useState(false)

  // Fetch eligible course data from the API (SPM + STPM)
  const fetchEligibleIds = useCallback(async () => {
    try {
      setEligibleLoading(true)
      const { ids: allIds, map: allMap } = await loadEligibleCourses()
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

  // Bumi coverage Sprint B: the eligible set was worked out under one Bumiputera answer. A new
  // answer drops it (and re-fetches when the toggle is on), so it never shows the old answer's.
  // Sprint D2: the pick-lists too — they load once, so they are dropped and re-loaded.
  const bumiSeen = useRef(bumi)
  useEffect(() => {
    if (bumiSeen.current === bumi) return
    bumiSeen.current = bumi
    setEligibleIds(null)
    setEligibleMap(null)
    setFilters(null)
    if (eligibleOnly) fetchEligibleIds()
  }, [bumi, eligibleOnly, fetchEligibleIds])

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
    if (aliran) params.set('aliran', aliran)
    const qs = params.toString()
    router.replace(qs ? `/search?${qs}` : '/search', { scroll: false })
  }, [query, level, field, sourceType, state, qualification, aliran, router])

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
        aliran: aliran || undefined,
        bumiputera: bumi || undefined,
        limit: 10000,
      })
      if (bumi !== bumiSeen.current) return   // asked under an older answer (Bumi D2): drop it
      setCourses(data.courses)
      setTotalCount(data.total_count)
      if (!filters) {
        setFilters(data.filters)
      }
    } catch {
      if (bumi !== bumiSeen.current) return
      setCourses([])
      setTotalCount(0)
    } finally {
      if (bumi === bumiSeen.current) setIsLoading(false)   // a dropped response leaves the newer one loading
    }
  }, [debouncedQuery, level, field, sourceType, state, qualification, aliran, bumi, filters])

  useEffect(() => {
    fetchCourses()
  }, [fetchCourses])

  // Reset display count when filters change
  useEffect(() => {
    setDisplayCount(COURSE_PAGE_SIZE)
  }, [debouncedQuery, level, field, sourceType, state, qualification, aliran, eligibleOnly])

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

  const hasActiveFilters = !!(query || level || field || sourceType || state || qualification || aliran)

  const clearAllFilters = () => {
    setQuery('')
    setLevel('')
    setField('')
    setSourceType('')
    setState('')
    setQualification('')
    setAliran('')
    setEligibleOnly(false)
  }

  // Aliran is a PISMP-only facet — selecting a non-IPGM source clears it.
  const handleSourceTypeChange = (value: string) => {
    setSourceType(value)
    if (value !== 'pismp') setAliran('')
  }

  // Source type labels for filter dropdown
  const SOURCE_LABELS: Record<string, string> = {
    ua: 'Universiti',
    pismp: 'IPGM',
    poly: 'Politeknik',
    iljtm: 'ILJTM',
    ilkbs: 'ILKBS',
    mara: 'MARA',
    tvet_other: 'Latihan Kemahiran',
    kkom: 'Kolej Komuniti',
    matric: 'Kolej Matrikulasi',
    stpm: 'Tingkatan 6',
  }

  // One list of facets for BOTH faces: the desktop pills and the phone sheet's chip groups.
  const typeOptions = (filters?.source_types ?? []).filter(t => t !== 'tvet').sort((a, b) =>
    (SOURCE_LABELS[a] ?? a).localeCompare(SOURCE_LABELS[b] ?? b, 'ms'))
  const alirans = filters?.alirans ?? []
  const fieldKeys = taxonomyLoaded
    ? [...fieldOptions].sort((a, b) => a.label.localeCompare(b.label, 'ms')).map(f => f.key)
    : (filters?.fields ?? [])
  const fieldLabels = taxonomyLoaded ? Object.fromEntries(fieldOptions.map(f => [f.key, f.label])) : undefined
  const option = (labels?: Record<string, string>) => (value: string) => ({ value, label: labels?.[value] ?? value })
  const facets: FacetGroup[] = [
    { key: 'qualification', title: t('search.qualification'), value: qualification, onChange: setQualification,
      options: ['SPM', 'STPM'].map(option()) },
    { key: 'type', title: t('search.allTypes'), value: sourceType, onChange: handleSourceTypeChange,
      options: typeOptions.map(option(SOURCE_LABELS)) },
    ...(sourceType === 'pismp' && alirans.length > 0 ? [{
      key: 'aliran', title: t('search.allAlirans'), value: aliran, onChange: setAliran,
      options: alirans.map(a => ({ value: a.value, label: a.label })) }] : []),
    { key: 'level', title: t('search.allLevels'), value: level, onChange: setLevel,
      options: (filters?.levels ?? []).map(option()) },
    { key: 'state', title: t('search.allStates'), value: state, onChange: setState, collapseAfter: 6,
      options: (filters?.states ?? []).map(option()) },
    { key: 'field', title: t('search.allFields'), value: field, onChange: setField, collapseAfter: 6,
      options: fieldKeys.map(option(fieldLabels)) },
  ]
  // The phone bar's "Filters · N" and its removable chips: every picked facet (not the words).
  const picked = facets.filter(f => f.value).map(f => ({
    key: f.key, label: f.options.find(o => o.value === f.value)?.label ?? f.value, clear: () => f.onChange(''),
  }))

  return (
    <main className="min-h-screen bg-ground-50">
      <AppHeader />

      <div className={`container mx-auto ${PHONE_GUTTER} py-4 md:py-8`}>
        {/* Header */}
        <div className="mb-3 md:mb-6">
          <h1 className="text-2xl font-bold text-ground-900 mb-1">
            {t('search.title')}
          </h1>
          {/* A phone spends its first screen on the search box and results (Mobile M3). */}
          <p className="hidden text-ground-600 text-sm sm:block">
            {t('search.subtitle')}
          </p>
        </div>

        {/* Search + Filter container */}
        <div className={`${PHONE_SECTION} mb-1 pt-0 md:pt-5`}>
          {/* Search bar — on a phone with the Filters button beside it */}
          <div className="mb-3 flex gap-2">
          <div className="relative min-w-0 flex-1">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-ground-400"
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
              type="search"
              className="w-full pl-10 px-4 py-3 rounded-lg border border-ground-200 bg-ground-50 focus:outline-none focus:ring-2 focus:ring-brand-shape focus:border-transparent placeholder:text-ground-placeholder"
              placeholder={t('search.searchPlaceholder')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {/* Phone: the filters live in a sheet (Mobile M3). The count is every picked facet. */}
          <button
            type="button"
            onClick={() => setFiltersOpen(true)}
            aria-haspopup="dialog"
            className="inline-flex h-12 shrink-0 items-center gap-2 rounded-lg border border-ground-300 bg-ground-0 px-3 text-sm font-medium text-ground-700 hover:bg-ground-50 md:hidden"
          >
            <svg className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M7 12h10M10 18h4" />
            </svg>
            {t('discovery.filters')}
            {picked.length > 0 && (
              <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-brand-fill px-1.5 text-xs font-semibold text-brand-fill-ink">
                {picked.length}
              </span>
            )}
          </button>
          </div>

          {/* Phone: what is picked, each removable with one tap (44 px), wrapping — never sideways. */}
          {picked.length > 0 && (
            <ul aria-label={t('discovery.activeFilters')} className="-mt-1 mb-2 flex flex-wrap gap-x-2 md:hidden">
              {picked.map(p => (
                <li key={p.key} className="min-w-0 max-w-full">
                  <button
                    type="button"
                    onClick={p.clear}
                    aria-label={t('discovery.removeFilter', { name: p.label })}
                    className="inline-flex min-h-11 max-w-full items-center"
                  >
                    <span className="inline-flex max-w-full items-center gap-1 rounded-full border border-brand-shape bg-primary-50 py-1 pl-3 pr-2 text-sm font-medium text-primary-700">
                      <span className="min-w-0 truncate">{p.label}</span>
                      <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                      </svg>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Filter row */}
          <div className="flex flex-wrap items-center gap-2">
          {/* The desktop's pills; a phone has the sheet above instead (Mobile M3). */}
          <div className="hidden md:contents">
          {/* Qualification filter — toggle buttons */}
          <div className="flex rounded-lg border border-ground-200 overflow-hidden">
            <button
              onClick={() => setQualification(qualification === 'SPM' ? '' : 'SPM')}
              className={`min-h-11 px-3 py-1.5 text-sm font-medium transition-colors ${
                qualification === 'SPM'
                  ? 'bg-brand-fill text-brand-fill-ink'
                  : 'bg-ground-0 text-ground-600 hover:bg-ground-50'
              }`}
            >
              SPM
            </button>
            <button
              onClick={() => setQualification(qualification === 'STPM' ? '' : 'STPM')}
              className={`min-h-11 px-3 py-1.5 text-sm font-medium transition-colors border-l border-ground-200 ${
                qualification === 'STPM'
                  ? 'bg-brand-fill text-brand-fill-ink'
                  : 'bg-ground-0 text-ground-600 hover:bg-ground-50'
              }`}
            >
              STPM
            </button>
          </div>

          <FilterPill
            label={t('search.allTypes')}
            value={sourceType}
            options={typeOptions}
            optionLabels={SOURCE_LABELS}
            onChange={handleSourceTypeChange}
          />

          {/* Aliran (school type) — PISMP/IPGM only */}
          {sourceType === 'pismp' && alirans.length > 0 && (
            <FilterPill
              label={t('search.allAlirans')}
              value={aliran}
              options={alirans.map(a => a.value)}
              optionLabels={Object.fromEntries(alirans.map(a => [a.value, a.label]))}
              onChange={setAliran}
            />
          )}

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
            options={fieldKeys}
            optionLabels={fieldLabels}
            onChange={setField}
          />

          {/* Clear Filters — always visible and blue */}
          <button
            onClick={clearAllFilters}
            disabled={!hasActiveFilters}
            className="min-h-11 px-3 py-1.5 text-sm font-medium text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-default"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            {t('search.clearFilters')}
          </button>

          {/* Spacer — pushes eligibility toggle right on desktop */}
          <div className="flex-1 min-w-0" />
          </div>

          {/* Eligibility toggle — prompts login if not authenticated. On a phone it stays HERE, in
              the bar, not in the filter sheet: a signed-out tap opens the sign-in sheet.
              ⚠ IT MAY SHRINK AND ITS TEXT WRAPS ON PURPOSE (TD-312). It was `flex-shrink-0`, so in
              Tamil its one-line description made /search 375 px wide on a 360 px phone. Only the
              switch itself keeps its size. `navLayout.test.ts` pins these classes. */}
          {thirdRoute ? (
            // Third results route S2b (D2): no entry rules exist for Matriculation / Asasi /
            // Diploma, so there is no "eligible" set to filter to — say so instead of showing none.
            <p className="min-w-0 max-w-sm break-words text-xs text-ground-500">{t('dashboard.higherBrowseNote')}</p>
          ) : (
          <button
            type="button"
            onClick={handleEligibleToggle}
            disabled={eligibleLoading}
            aria-pressed={eligibleOnly}
            className="flex min-h-11 items-center gap-2 min-w-0 max-w-full cursor-pointer disabled:opacity-60"
          >
            <div className="relative inline-flex items-center shrink-0">
              <div className={clsx(
                'w-10 h-5 rounded-full transition-colors',
                eligibleOnly ? 'bg-brand-shape' : 'bg-ground-200'
              )} />
              <div className={clsx(
                'absolute top-0.5 left-0.5 w-4 h-4 bg-ground-0 rounded-full shadow-sm transition-transform',
                eligibleOnly && 'translate-x-5'
              )} />
            </div>
            <div className="min-w-0 break-words text-sm text-left">
              <span className="font-medium text-ground-700">{t('search.eligibleOnly')}</span>
              <span className="block text-xs text-ground-400">{t('search.eligibleToggleDesc')}</span>
            </div>
          </button>
          )}
          </div>
        </div>

        <SearchFilterSheet
          open={filtersOpen}
          onClose={() => setFiltersOpen(false)}
          groups={facets}
          resultCount={isLoading ? null : displayedCourses.length}
          // The sheet's Clear clears what the sheet holds — not the search words or the switch.
          // aliran too: a hand-typed `?aliran=` without `type=pismp` filters the results while its group is
          // hidden, so it has no chip and no count — Clear must still remove it (M3 review).
          onClear={() => { picked.forEach(p => p.clear()); setAliran('') }}
          canClear={picked.length > 0}
        />

        {/* Results meta */}
        <div className="mb-4">
          <p className="text-sm text-ground-600">
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
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-brand-shape border-t-transparent mb-4" />
            <p className="text-ground-600">{t('common.loading')}</p>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && displayedCourses.length === 0 && (
          <div className="text-center py-12">
            <p className="text-ground-600 mb-2">{t('search.noCourses')}</p>
            <p className="text-ground-400 text-sm">{t('search.tryDifferent')}</p>
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
                    if (!isAuthenticated) {
                      if (!hasGrades()) { router.push('/onboarding/exam-type'); return }
                      showAuthGate('loadmore'); return
                    }
                    setDisplayCount(displayCount + COURSE_PAGE_SIZE)
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
