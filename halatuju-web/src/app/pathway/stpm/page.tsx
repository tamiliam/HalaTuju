'use client'

import { useEffect, useState, useMemo, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'
import { calculatePathways, type PathwayResult } from '@/lib/api'
import { STPM_SCHOOLS, type StpmSchool } from '@/data/stpm-schools'
import { KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS } from '@/lib/storage'

const PAGE_SIZE = 50

type StreamId = 'sains' | 'sains_sosial'

const STREAM_META: Record<StreamId, {
  label: string
  badgeColor: string
  schoolStream: string
}> = {
  sains: {
    label: 'Science',
    badgeColor: 'bg-green-100 text-green-800',
    schoolStream: 'Sains',
  },
  sains_sosial: {
    label: 'Social Science',
    badgeColor: 'bg-sky-100 text-sky-800',
    schoolStream: 'Sains Sosial',
  },
}

function mataGredColor(mg: number | undefined | null): string {
  if (mg === undefined || mg === null) return 'text-gray-500'
  if (mg <= 6) return 'text-green-600'
  if (mg <= 12) return 'text-amber-600'
  return 'text-red-600'
}

export default function StpmDetailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
      </div>
    }>
      <StpmContent />
    </Suspense>
  )
}

function StpmContent() {
  const { t } = useT()
  const searchParams = useSearchParams()
  const streamParam = searchParams.get('stream') as StreamId | null

  const [profile, setProfile] = useState<{
    grades: Record<string, string>
    coqScore: number
  } | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [stateFilter, setStateFilter] = useState('')
  const [ppdFilter, setPpdFilter] = useState('')
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)

  // Load profile from localStorage
  useEffect(() => {
    const gradesStr = localStorage.getItem(KEY_GRADES)
    const profileStr = localStorage.getItem(KEY_PROFILE)

    if (gradesStr && profileStr) {
      const grades = JSON.parse(gradesStr)
      const parsed = JSON.parse(profileStr)
      setProfile({
        grades,
        coqScore: parsed.coqScore ?? 5.0,
      })
    }

    setIsLoading(false)
  }, [])

  // Run pathway engine via API
  const [stpmResults, setStpmResults] = useState<PathwayResult[]>([])
  const [pathwayLoading, setPathwayLoading] = useState(true)

  useEffect(() => {
    if (!profile) {
      setPathwayLoading(false)
      return
    }

    const fetchPathways = async () => {
      setPathwayLoading(true)
      try {
        const signals = JSON.parse(localStorage.getItem(KEY_QUIZ_SIGNALS) || 'null')
        const { pathways } = await calculatePathways(profile.grades, profile.coqScore, signals)
        setStpmResults(pathways.filter(p => p.pathway === 'stpm'))
      } catch {
        setStpmResults([])
      } finally {
        setPathwayLoading(false)
      }
    }

    fetchPathways()
  }, [profile])

  const eligibleResults = useMemo(
    () => stpmResults.filter((r) => r.eligible),
    [stpmResults]
  )

  // Determine active stream: URL param > first eligible > sains
  const activeStream: StreamId = useMemo(() => {
    if (streamParam && (streamParam === 'sains' || streamParam === 'sains_sosial')) {
      return streamParam
    }
    if (eligibleResults.length > 0) {
      return eligibleResults[0].trackId as StreamId
    }
    return 'sains'
  }, [streamParam, eligibleResults])

  // Current stream result from engine
  const currentResult = useMemo(
    () => stpmResults.find((r) => r.trackId === activeStream),
    [stpmResults, activeStream]
  )

  const meta = STREAM_META[activeStream]

  // Stream display names
  const streamName = activeStream === 'sains'
    ? t('pathwayDetail.sains')
    : t('pathwayDetail.sainsSosial')

  // About text
  const aboutText = activeStream === 'sains'
    ? 'The STPM Science stream (Aliran Sains) is a 1.5-year pre-university programme at government secondary schools. Students take 3 science subjects plus Pengajian Am. STPM is internationally recognised and accepted by universities worldwide.'
    : 'The STPM Social Science stream (Aliran Sains Sosial) covers humanities and commerce subjects. Students choose 3 subjects from Economics, Business Studies, Accounting, Geography, History, Literature, and more, plus Pengajian Am.'

  const subtitleText = activeStream === 'sains'
    ? 'Pre-university science stream covering Biology, Chemistry, Physics, and Mathematics'
    : 'Pre-university arts stream covering Economics, Business, Accounting, Geography, and more'

  // Filter schools: only those offering THIS stream
  const streamSchools = useMemo(() => {
    return STPM_SCHOOLS.filter((s) =>
      s.streams.includes(meta.schoolStream)
    )
  }, [meta.schoolStream])

  // Unique states from filtered schools
  const allStates = useMemo(() => {
    const states = new Set<string>()
    streamSchools.forEach((s) => states.add(s.state))
    return Array.from(states).sort()
  }, [streamSchools])

  // PPDs from filtered schools (further filtered by state if selected)
  const availablePpds = useMemo(() => {
    let schools = streamSchools
    if (stateFilter) {
      schools = schools.filter((s) => s.state === stateFilter)
    }
    const ppds = new Set<string>()
    schools.forEach((s) => ppds.add(s.ppd))
    return Array.from(ppds).sort()
  }, [streamSchools, stateFilter])

  // Apply state + PPD filters
  const filteredSchools = useMemo(() => {
    let schools = streamSchools

    if (stateFilter) {
      schools = schools.filter((s) => s.state === stateFilter)
    }
    if (ppdFilter) {
      schools = schools.filter((s) => s.ppd === ppdFilter)
    }

    return schools
  }, [streamSchools, stateFilter, ppdFilter])

  const displayedSchools = filteredSchools.slice(0, displayCount)
  const remaining = filteredSchools.length - displayCount

  // Reset filters when stream changes
  useEffect(() => {
    setStateFilter('')
    setPpdFilter('')
    setDisplayCount(PAGE_SIZE)
  }, [activeStream])

  // Reset PPD when state changes
  useEffect(() => {
    setPpdFilter('')
    setDisplayCount(PAGE_SIZE)
  }, [stateFilter])

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
          <p className="text-gray-600">{t('common.loading')}</p>
        </div>
      </main>
    )
  }

  if (!profile) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            {t('dashboard.noProfile')}
          </h1>
          <p className="text-gray-600 mb-6">
            {t('dashboard.noProfileDesc')}
          </p>
          <Link href="/onboarding/exam-type" className="btn-primary">
            {t('dashboard.startOnboarding')}
          </Link>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50 overflow-x-hidden">
      <AppHeader />

      {/* Header Section */}
      <section className="bg-white border-b">
        <div className="container mx-auto px-4 sm:px-6 py-6 sm:py-8">
          {/* Back link */}
          <Link
            href="/dashboard"
            className="text-sm text-primary-500 hover:text-primary-700 mb-4 inline-block"
          >
            &larr; {t('pathwayDetail.backToDashboard')}
          </Link>

          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-700">
                Form 6
              </span>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${meta.badgeColor}`}>
                {streamName}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-2">
              Form 6 (STPM) — {streamName}
            </h1>

            <p className="text-sm sm:text-lg text-primary-600 font-medium mb-4">
              {subtitleText}
            </p>

            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                3 Semesters
              </span>
              <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                Free
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <div className="container mx-auto px-4 sm:px-6 py-6 sm:py-8">
        <div className="grid md:grid-cols-3 gap-6">
          {/* Left Column */}
          <div className="md:col-span-2 space-y-6">
            {/* About This Stream */}
            <section className="bg-white rounded-xl border border-gray-200 p-4 sm:p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                About This Stream
              </h2>
              <p className="text-sm sm:text-base text-gray-600 leading-relaxed break-words">
                {aboutText}
              </p>
            </section>

            {/* Where to Study */}
            <section className="bg-white rounded-xl border border-gray-200 p-4 sm:p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                {t('courseDetail.whereToStudy')}
                <span className="text-gray-500 font-normal ml-2">
                  ({filteredSchools.length})
                </span>
              </h2>

              {/* Filters */}
              <div className="flex flex-wrap gap-3 mb-4">
                <select
                  value={stateFilter}
                  onChange={(e) => setStateFilter(e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="">{t('pathwayDetail.allStates')}</option>
                  {allStates.map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </select>

                <select
                  value={ppdFilter}
                  onChange={(e) => {
                    setPpdFilter(e.target.value)
                    setDisplayCount(PAGE_SIZE)
                  }}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="">All Districts</option>
                  {availablePpds.map((ppd) => (
                    <option key={ppd} value={ppd}>
                      {ppd}
                    </option>
                  ))}
                </select>
              </div>

              {/* School List */}
              <div className="max-h-[600px] overflow-y-auto space-y-3">
                {displayedSchools.length > 0 ? (
                  displayedSchools.map((school) => (
                    <SchoolCard key={school.code} school={school} activeStream={meta.schoolStream} />
                  ))
                ) : (
                  <p className="text-gray-400 text-center py-8">
                    No schools match the selected filters.
                  </p>
                )}
              </div>

              {/* Load More */}
              {remaining > 0 && (
                <div className="text-center pt-4">
                  <button
                    className="btn-secondary"
                    onClick={() => setDisplayCount(displayCount + PAGE_SIZE)}
                  >
                    {t('dashboard.loadMore')} ({remaining} {t('dashboard.remaining')})
                  </button>
                </div>
              )}
            </section>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Quick Facts */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {t('courseDetail.quickFacts')}
              </h2>
              <div className="space-y-4">
                <InfoRow label="Programme" value="Form 6 (STPM)" />
                <InfoRow label={t('pathwayDetail.stream')} value={streamName} />
                <InfoRow label="Duration" value="3 Semesters" />
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-sm">Fee</span>
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                    Free
                  </span>
                </div>
                {currentResult?.mataGred != null && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 text-sm">{t('pathwayDetail.mataGred')}</span>
                    <span className={`font-bold ${mataGredColor(currentResult.mataGred)}`}>
                      {currentResult.mataGred}
                      {currentResult.maxMataGred != null && (
                        <span className="text-gray-400 font-normal text-xs ml-1">
                          / {currentResult.maxMataGred}
                        </span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </section>

            {/* Subject Legend */}
            <SubjectLegend stream={meta.schoolStream} />

            {/* Caveat */}
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-xs text-amber-700">
                {t('pathwayDetail.stpmCaveat')}
              </p>
            </div>
          </div>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-gray-500 text-sm">{label}</span>
      <span className="font-medium text-gray-900 text-sm">{value}</span>
    </div>
  )
}

const COMMON_SUBJECTS = new Set(['BI (MUET)', 'PA', 'BM'])
const SCIENCE_SUBJECTS = new Set(['BIO', 'CHE', 'PHY', 'MT', 'MM'])
const SOCIAL_SUBJECTS = new Set(['EKO', 'SEJ', 'GEO', 'PP', 'PAKN', 'SS', 'SV', 'BT', 'BC', 'KMK', 'ICT', 'L.ENG'])

const SUBJECT_COLORS: Record<string, string> = {
  BIO: 'bg-green-100 text-green-700',
  CHE: 'bg-amber-100 text-amber-700',
  PHY: 'bg-blue-100 text-blue-700',
  MT: 'bg-indigo-100 text-indigo-700',
  MM: 'bg-indigo-100 text-indigo-700',
  EKO: 'bg-emerald-100 text-emerald-700',
  SEJ: 'bg-rose-100 text-rose-700',
  GEO: 'bg-teal-100 text-teal-700',
  PP: 'bg-orange-100 text-orange-700',
  PAKN: 'bg-purple-100 text-purple-700',
  SS: 'bg-pink-100 text-pink-700',
  SV: 'bg-cyan-100 text-cyan-700',
  BT: 'bg-red-100 text-red-700',
  BC: 'bg-yellow-100 text-yellow-700',
  KMK: 'bg-fuchsia-100 text-fuchsia-700',
  ICT: 'bg-sky-100 text-sky-700',
  'L.ENG': 'bg-lime-100 text-lime-700',
}

const SUBJECT_NAMES: Record<string, string> = {
  BIO: 'Biology',
  CHE: 'Chemistry',
  PHY: 'Physics',
  MT: 'Mathematics (T)',
  MM: 'Mathematics (M)',
  EKO: 'Economics',
  SEJ: 'History',
  GEO: 'Geography',
  PP: 'Business Studies',
  PAKN: 'Accounting',
  SS: 'Literature',
  SV: 'Visual Arts',
  BT: 'Bahasa Tamil',
  BC: 'Bahasa Cina',
  KMK: 'Kesusasteraan Melayu Komunikatif',
  ICT: 'Information & Communication Technology',
  'L.ENG': 'Literature in English',
}

function filterSubjects(raw: string, stream: string): string[] {
  const relevant = stream === 'Sains' ? SCIENCE_SUBJECTS : SOCIAL_SUBJECTS
  return raw
    .split('; ')
    .filter(s => !COMMON_SUBJECTS.has(s) && relevant.has(s))
}

function formatPhone(raw: string): string {
  const d = raw.replace(/\D/g, '')
  if (d.length === 10) return `${d.slice(0, 3)}-${d.slice(3, 6)} ${d.slice(6)}`
  if (d.length === 9) return `${d.slice(0, 2)}-${d.slice(2, 5)} ${d.slice(5)}`
  if (d.length === 11) return `${d.slice(0, 3)}-${d.slice(3, 7)} ${d.slice(7)}`
  return raw
}

function SubjectLegend({ stream }: { stream: string }) {
  const subjects = stream === 'Sains'
    ? ['BIO', 'CHE', 'PHY', 'MT', 'MM']
    : ['EKO', 'PP', 'PAKN', 'SEJ', 'GEO', 'SS', 'SV', 'BT', 'BC', 'KMK', 'ICT', 'L.ENG']

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">Subject Key</h2>
      <div className="space-y-2">
        {subjects.map(code => (
          <div key={code} className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${SUBJECT_COLORS[code]}`}>
              {code}
            </span>
            <span className="text-xs text-gray-600">{SUBJECT_NAMES[code]}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function SchoolCard({ school, activeStream }: { school: StpmSchool; activeStream: string }) {
  const subjects = school.subjects ? filterSubjects(school.subjects, activeStream) : []

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 text-sm sm:text-base mb-1 truncate">
            {school.name}
          </h3>
          <p className="text-xs sm:text-sm text-gray-500 mb-2">
            {school.state} &middot; {school.ppd}
          </p>
          {subjects.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {subjects.map(s => (
                <span key={s} className={`px-1.5 py-0.5 rounded text-[10px] sm:text-xs font-medium ${SUBJECT_COLORS[s] || 'bg-gray-100 text-gray-600'}`}>
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
        {school.phone && (
          <a
            href={`tel:${school.phone}`}
            className="text-xs sm:text-sm text-primary-600 hover:text-primary-800 whitespace-nowrap flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            {formatPhone(school.phone)}
          </a>
        )}
      </div>
    </div>
  )
}
