'use client'

import { useEffect, useState, useMemo, Suspense } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { calculatePathways, type PathwayResult } from '@/lib/api'
import { MATRIC_COLLEGES, type MatricCollege } from '@/data/matric-colleges'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS } from '@/lib/storage'

type TrackId = 'sains' | 'sains_komputer' | 'kejuruteraan' | 'perakaunan'

const TRACK_COLOURS: Record<TrackId, string> = {
  sains: 'bg-green-100 text-green-800',
  sains_komputer: 'bg-blue-100 text-blue-800',
  kejuruteraan: 'bg-orange-100 text-orange-800',
  perakaunan: 'bg-purple-100 text-purple-800',
}

const TRACK_I18N_KEYS: Record<TrackId, string> = {
  sains: 'pathwayDetail.sains',
  sains_komputer: 'pathwayDetail.sainsKomputer',
  kejuruteraan: 'pathwayDetail.kejuruteraan',
  perakaunan: 'pathwayDetail.perakaunan',
}

const TRACK_SUBTITLES: Record<TrackId, string> = {
  sains: 'Pre-university science programme covering Physics, Chemistry, Biology, and Mathematics',
  sains_komputer: 'Pre-university programme in Computer Science and Information Technology',
  kejuruteraan: 'Pre-university engineering programme covering technical and applied sciences',
  perakaunan: 'Pre-university accounting programme covering business and financial studies',
}

const TRACK_DESCRIPTIONS: Record<TrackId, string> = {
  sains: 'The Matriculation Science track (Jurusan Sains) is a one-year pre-university programme under the Ministry of Education (KPM). Students study Physics, Chemistry, Biology, Mathematics, Computer Science, and Soft Skills. Graduates can apply for science-based degree programmes at public universities.',
  sains_komputer: 'The Computer Science track (Jurusan Sains Komputer) focuses on programming, data structures, and IT fundamentals alongside Mathematics and core science subjects. Available at 4 selected colleges only.',
  kejuruteraan: 'The Engineering track (Jurusan Kejuruteraan) is offered at 3 dedicated engineering colleges (Kolej Matrikulasi Kejuruteraan). Students study Engineering Mathematics, Physics, Chemistry, and Engineering Technology.',
  perakaunan: 'The Accounting track (Jurusan Perakaunan) covers Accounting, Economics, Business Management, and Mathematics. Graduates can pursue accounting and business degree programmes.',
}

const ALL_TRACK_IDS: TrackId[] = ['sains', 'sains_komputer', 'kejuruteraan', 'perakaunan']

function MatricPageContent() {
  const { t } = useT()
  const searchParams = useSearchParams()
  const [grades, setGrades] = useState<Record<string, string> | null>(null)
  const [coq, setCoq] = useState<number>(0)
  const [stateFilter, setStateFilter] = useState<string>('all')

  // Load profile from localStorage
  useEffect(() => {
    const gradesRaw = localStorage.getItem(KEY_GRADES)
    const profileRaw = localStorage.getItem(KEY_PROFILE)

    if (gradesRaw && profileRaw) {
      setGrades(JSON.parse(gradesRaw))
      const profile = JSON.parse(profileRaw)
      setCoq(profile.coqScore ?? profile.coq ?? 5.0)
    }
  }, [])

  // Run pathway engine via API
  const [matricResults, setMatricResults] = useState<PathwayResult[]>([])
  const [pathwayLoading, setPathwayLoading] = useState(true)

  useEffect(() => {
    if (!grades || Object.keys(grades).length === 0) {
      setPathwayLoading(false)
      return
    }

    const fetchPathways = async () => {
      setPathwayLoading(true)
      try {
        const signals = JSON.parse(localStorage.getItem(KEY_QUIZ_SIGNALS) || 'null')
        const { pathways } = await calculatePathways(grades, coq, signals)
        setMatricResults(pathways.filter(p => p.pathway === 'matric'))
      } catch {
        setMatricResults([])
      } finally {
        setPathwayLoading(false)
      }
    }

    fetchPathways()
  }, [grades, coq])

  // Determine current track from URL param or first eligible
  const currentTrackId = useMemo((): TrackId => {
    const param = searchParams.get('track') as TrackId | null
    if (param && ALL_TRACK_IDS.includes(param)) return param
    // Fall back to first eligible track
    const firstEligible = matricResults.find(r => r.eligible)
    if (firstEligible) return firstEligible.trackId as TrackId
    return 'sains'
  }, [searchParams, matricResults])

  // Current track result
  const currentResult = useMemo(
    () => matricResults.find(r => r.trackId === currentTrackId),
    [matricResults, currentTrackId]
  )

  // Current track info from API results
  const currentTrack = useMemo(() => {
    const r = matricResults.find(r => r.trackId === currentTrackId)
    if (!r) return null
    return { id: r.trackId, name: r.trackName, name_ms: r.trackNameMs, name_ta: r.trackNameTa }
  }, [matricResults, currentTrackId])

  // Merit score for current track
  const meritScore = currentResult?.merit ?? null

  // Merit band
  const meritBand = useMemo(() => {
    if (meritScore === null) return null
    if (meritScore >= 94) return { label: t('pathwayDetail.high'), colour: 'text-green-700' }
    if (meritScore >= 89) return { label: t('pathwayDetail.fair'), colour: 'text-amber-700' }
    return { label: t('pathwayDetail.low'), colour: 'text-red-700' }
  }, [meritScore, t])

  // Filter colleges: must offer THIS specific track
  const trackColleges = useMemo(() => {
    let colleges = MATRIC_COLLEGES.filter(c =>
      c.tracks.includes(currentTrackId)
    )
    if (stateFilter !== 'all') {
      colleges = colleges.filter(c => c.state === stateFilter)
    }
    return colleges
  }, [currentTrackId, stateFilter])

  // Available states from track-filtered colleges (before state filter)
  const availableStates = useMemo(() => {
    const trackFilteredColleges = MATRIC_COLLEGES.filter(c =>
      c.tracks.includes(currentTrackId)
    )
    return Array.from(new Set(trackFilteredColleges.map(c => c.state))).sort()
  }, [currentTrackId])

  // Loading / no profile state
  if (!grades) {
    return (
      <main className="min-h-screen bg-gray-50">
        <AppHeader />
        <div className="flex items-center justify-center py-24">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
            <p className="text-gray-600">{t('common.loadingProfile')}</p>
          </div>
        </div>
        <AppFooter />
      </main>
    )
  }

  const trackName = currentTrack?.name ?? currentTrackId

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      {/* Back link */}
      <div className="container mx-auto px-4 sm:px-6 pt-6">
        <Link
          href="/dashboard"
          className="inline-flex items-center text-sm text-gray-500 hover:text-primary-600"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          {t('pathwayDetail.backToDashboard')}
        </Link>
      </div>

      {/* Header section */}
      <section className="bg-white border-b mt-4">
        <div className="container mx-auto px-4 sm:px-6 py-8">
          <div className="flex-1">
            {/* Badges */}
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-700">
                {t('pathwayDetail.matricTitle')}
              </span>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${TRACK_COLOURS[currentTrackId]}`}>
                {t(TRACK_I18N_KEYS[currentTrackId])}
              </span>
            </div>

            {/* Title */}
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {t('pathwayDetail.matricTitle')} &mdash; {t(TRACK_I18N_KEYS[currentTrackId])}
            </h1>

            {/* Subtitle */}
            <p className="text-lg text-primary-600 font-medium mb-4">
              {TRACK_SUBTITLES[currentTrackId]}
            </p>

            {/* Duration + Fee */}
            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                2 Semesters
              </span>
              <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                Free
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content — Two-column layout */}
      <div className="container mx-auto px-4 sm:px-6 py-8">
        <div className="grid md:grid-cols-3 gap-6">

          {/* Left column */}
          <div className="md:col-span-2 space-y-6">

            {/* About This Track */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                About This Track
              </h2>
              <p className="text-gray-600 leading-relaxed">
                {TRACK_DESCRIPTIONS[currentTrackId]}
              </p>
            </section>

            {/* Where to Study */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  {t('pathwayDetail.colleges')}
                  <span className="text-gray-400 font-normal ml-2 text-base">
                    ({trackColleges.length})
                  </span>
                </h2>

                {/* State filter */}
                <select
                  value={stateFilter}
                  onChange={e => setStateFilter(e.target.value)}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="all">{t('pathwayDetail.allStates')}</option>
                  {availableStates.map(state => (
                    <option key={state} value={state}>{state}</option>
                  ))}
                </select>
              </div>

              {trackColleges.length > 0 ? (
                <div className="space-y-3">
                  {trackColleges.map(college => (
                    <CollegeCard
                      key={college.id}
                      college={college}
                      currentTrackId={currentTrackId}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 text-center py-8">
                  No colleges found for the selected filters.
                </p>
              )}
            </section>
          </div>

          {/* Right column */}
          <div className="space-y-6">

            {/* Quick Facts */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Quick Facts
              </h2>
              <div className="space-y-4">
                <InfoRow label="Programme" value={t('pathwayDetail.matricTitle')} />
                <InfoRow label="Track" value={t(TRACK_I18N_KEYS[currentTrackId])} />
                <InfoRow label="Duration" value="2 Semesters" />
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-sm">Fee</span>
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                    Free
                  </span>
                </div>
                <InfoRow label="Intake" value="March (yearly)" />
                {meritScore !== null && meritBand && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 text-sm">{t('pathwayDetail.meritScore')}</span>
                    <span className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900 text-sm">{meritScore}</span>
                      <span className={`text-xs font-medium ${meritBand.colour}`}>
                        ({meritBand.label})
                      </span>
                    </span>
                  </div>
                )}
              </div>
            </section>

            {/* Caveat card */}
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="flex gap-3">
                <svg className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                <p className="text-sm text-amber-800">
                  {t('pathwayDetail.matricCaveat')}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}

export default function MatricPathwayPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </main>
    }>
      <MatricPageContent />
    </Suspense>
  )
}

// --- Sub-components ---

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-gray-500 text-sm">{label}</span>
      <span className="font-medium text-gray-900 text-sm">{value}</span>
    </div>
  )
}

function CollegeCard({
  college,
  currentTrackId,
}: {
  college: MatricCollege
  currentTrackId: TrackId
}) {
  const { t } = useT()

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      {/* College name */}
      <h3 className="font-semibold text-gray-900 mb-2">{college.name}</h3>

      {/* State */}
      <div className="flex items-center gap-1.5 text-sm text-gray-500 mb-3">
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        {college.state}
      </div>

      {/* Track badge — show only the active track */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${TRACK_COLOURS[currentTrackId]}`}
        >
          {t(TRACK_I18N_KEYS[currentTrackId])}
        </span>
      </div>

      {/* Phone */}
      <div className="flex items-center gap-2 text-sm text-gray-600 mb-1.5">
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
        </svg>
        {college.phone}
      </div>

      {/* Website */}
      <a
        href={`https://${college.website}`}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 hover:underline"
      >
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
        {college.website}
      </a>
    </div>
  )
}
