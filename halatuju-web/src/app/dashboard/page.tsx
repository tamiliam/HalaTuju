'use client'

import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import {
  checkEligibility,
  checkStpmEligibility,
  rankStpmCourses,
  getRankedResults,
  generateReport,
  getReports,
  type StudentProfile,
  type EligibleCourse,
  type RankedCourse,
  type RankingResult,
  type StpmRankedCourse,
} from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useSavedCourses } from '@/hooks/useSavedCourses'
import CourseCard from '@/components/CourseCard'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import ScholarshipBanner from '@/components/ScholarshipBanner'
import { useT } from '@/lib/i18n'
import PathwayCards, { type PathwaySummary } from '@/components/PathwayCards'
import { useToast } from '@/components/Toast'
import { KEY_RESUME_ACTION, KEY_QUIZ_SIGNALS, KEY_REPORT_GENERATED, KEY_STPM_QUIZ_SIGNALS, COURSE_PAGE_SIZE } from '@/lib/storage'
import type { StpmResultFraming } from '@/lib/api'
import { useOnboardingGuard } from '@/lib/useOnboardingGuard'
import { useCachedResults } from '@/hooks/useCachedResults'

function getMeritLevel(studentMerit: number, courseMerit: number | null | undefined): 'high' | 'fair' | 'low' | 'none' {
  if (courseMerit === null || courseMerit === undefined) return 'none'
  if (studentMerit >= courseMerit) return 'high'
  if (studentMerit >= courseMerit - 5) return 'fair'
  return 'low'
}

const MERIT_STYLES = {
  high: 'bg-positive-100 text-positive-800',
  fair: 'bg-caution-100 text-caution-800',
  low: 'bg-critical-100 text-critical-800',
  none: 'bg-ground-100 text-ground-600',
}
const MERIT_LABELS = { high: 'High', fair: 'Fair', low: 'Low', none: '—' }

export default function DashboardPage() {
  const { t } = useT()
  const router = useRouter()
  const { ready: onboarded, loading: guardLoading, needsNric } = useOnboardingGuard()
  // `authProfile` is the SERVER's profile (AuthProvider). Named apart from the local `profile`
  // below, which is what this browser has cached — the two disagreeing is what request #11 was.
  const { isAuthenticated, token, showAuthGate, profile: authProfile } = useAuth()
  const { savedIds, toggleSave: handleSaveOrGate } = useSavedCourses()
  const { showToast } = useToast()
  // What THIS BROWSER holds, re-read when the server profile lands. Derived, not copied into
  // state: five useStates fed by one effect is what let the page hold an answer the cache had
  // already contradicted. See `useCachedResults` and `resolveCachedResults`.
  const { results: cached, ready: cacheReady } = useCachedResults(authProfile)
  const profile: StudentProfile | null =
    cached.view === 'stpm' || cached.view === 'spm' ? cached.profile : null
  const stpmData = cached.view === 'stpm' ? cached.stpm : null
  const examType: 'spm' | 'stpm' = cached.view === 'stpm' ? 'stpm' : 'spm'
  // Declared STPM, results not entered yet, nothing to fall back on. NOT the same as "no profile".
  const stpmPending = cached.view === 'stpm_pending'
  const isLoading = !cacheReady
  const [filter, setFilter] = useState<string>('all')
  const [displayCount, setDisplayCount] = useState(COURSE_PAGE_SIZE)
  const [quizSignals, setQuizSignals] = useState<Record<string, Record<string, number>> | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState(false)
  const [existingReportId, setExistingReportId] = useState<number | null>(null)
  const [reportGenerated, setReportGenerated] = useState(false)
  const [stpmResults, setStpmResults] = useState<StpmRankedCourse[] | null>(null)
  const [stpmFraming, setStpmFraming] = useState<StpmResultFraming | null>(null)

  // The two cached values that are NOT results — read on the same signal, for the same reason.
  useEffect(() => {
    const signals = localStorage.getItem(KEY_QUIZ_SIGNALS)
    if (signals) {
      try { setQuizSignals(JSON.parse(signals)) } catch { /* malformed — ignore */ }
    }
    setReportGenerated(localStorage.getItem(KEY_REPORT_GENERATED) === 'true')
  }, [authProfile])

  // Check STPM eligibility when stpmData is available
  useEffect(() => {
    if (examType !== 'stpm' || !stpmData || !profile) return

    const genderMap: Record<string, string> = { male: 'Lelaki', female: 'Perempuan' }
    const nationalityMap: Record<string, string> = { malaysian: 'Warganegara', non_malaysian: 'Bukan Warganegara' }

    checkStpmEligibility({
      stpm_grades: stpmData.stpmGrades,
      spm_grades: stpmData.spmGrades,
      cgpa: stpmData.cgpa,
      muet_band: stpmData.muetBand,
      gender: genderMap[profile.gender] || '',
      nationality: nationalityMap[profile.nationality] || 'Warganegara',
      colorblind: !!profile.colorblind,
    }).then(data => {
      // Chain ranking after eligibility — use STPM quiz signals if available
      const stpmSignalsStr = localStorage.getItem(KEY_STPM_QUIZ_SIGNALS)
      const spmSignalsStr = localStorage.getItem(KEY_QUIZ_SIGNALS)
      const signals = stpmSignalsStr ? JSON.parse(stpmSignalsStr)
        : spmSignalsStr ? JSON.parse(spmSignalsStr) : {}
      if (stpmSignalsStr) setQuizSignals(JSON.parse(stpmSignalsStr))
      return rankStpmCourses({
        eligible_courses: data.eligible_courses,
        student_cgpa: stpmData.cgpa,
        student_signals: signals,
        stpm_subjects: Object.keys(stpmData.stpmGrades),
      })
    }).then(ranked => {
      setStpmResults(ranked.ranked_courses)
      if (ranked.framing) setStpmFraming(ranked.framing)
    }).catch(() => {
      showToast('Failed to load STPM results. Please try again.', 'error')
      setStpmResults([])
    })
  }, [examType, stpmData, profile])

  // Check for existing reports when token becomes available
  useEffect(() => {
    if (!token) return
    getReports({ token })
      .then(({ reports }) => {
        if (reports.length > 0) {
          setExistingReportId(reports[0].report_id)
          // Sync reportGenerated with DB: if report exists and localStorage
          // doesn't say otherwise (quiz retake clears KEY_REPORT_GENERATED),
          // mark as generated so the button stays hidden
          const localFlag = localStorage.getItem(KEY_REPORT_GENERATED)
          if (localFlag === null) {
            // No local flag — either fresh device or quiz retake cleared it.
            // Quiz retake also stores fresh quiz signals, so if signals are
            // absent we know this is a fresh device → hide Generate button.
            if (!localStorage.getItem(KEY_QUIZ_SIGNALS)) {
              setReportGenerated(true)
            }
          }
        }
      })
      .catch(() => {})
  }, [token])

  // Query eligibility when profile is ready
  const {
    data: eligibilityData,
    isLoading: eligibilityLoading,
    error,
  } = useQuery({
    queryKey: ['eligibility', profile],
    queryFn: () => checkEligibility(profile!),
    enabled: !!profile,
  })

  // Query ranking when eligibility + quiz signals are both ready
  const {
    data: rankingData,
    isLoading: rankingLoading,
  } = useQuery({
    queryKey: ['ranking', eligibilityData?.eligible_courses, quizSignals],
    queryFn: () => getRankedResults(eligibilityData!.eligible_courses, quizSignals!),
    enabled: !!eligibilityData && !!quizSignals,
  })

  // Build pathway summary badges from eligibility data
  const pathwaySummaries = useMemo((): PathwaySummary[] => {
    const summaries: PathwaySummary[] = []

    // Course counts from API response (uses pathway_type from backend)
    const courseCounts: Record<string, number> = {}
    if (eligibilityData?.eligible_courses) {
      eligibilityData.eligible_courses.forEach((c: { pathway_type?: string; source_type: string }) => {
        const pt = c.pathway_type || c.source_type
        courseCounts[pt] = (courseCounts[pt] || 0) + 1
      })
    }

    const orderedPathways: { type: PathwaySummary['type']; count: number }[] = [
      { type: 'matric', count: courseCounts['matric'] || 0 },
      { type: 'stpm', count: courseCounts['stpm'] || 0 },
      { type: 'asasi', count: courseCounts['asasi'] || 0 },
      { type: 'pismp', count: courseCounts['pismp'] || 0 },
      { type: 'poly', count: courseCounts['poly'] || 0 },
      { type: 'university', count: courseCounts['university'] || 0 },
      { type: 'kkom', count: courseCounts['kkom'] || 0 },
      { type: 'iljtm', count: courseCounts['iljtm'] || 0 },
      { type: 'ilkbs', count: courseCounts['ilkbs'] || 0 },
    ]

    for (const { type, count } of orderedPathways) {
      if (count > 0) {
        summaries.push({
          type,
          label: t(`pathways.types.${type}`),
          count,
          eligible: true,
        })
      }
    }

    return summaries
  }, [eligibilityData, t])

  const handleRetakeQuiz = () => {
    // Navigate to quiz — old signals stay in force until new quiz completes
    router.push('/quiz')
  }

  const handleGenerateReport = useCallback(async () => {
    if (!eligibilityData) return
    if (!isAuthenticated || !token) {
      showAuthGate('report')
      return
    }
    setReportLoading(true)
    setReportError(false)
    try {
      const result = await generateReport(
        eligibilityData.eligible_courses,
        eligibilityData.insights,
        'bm',
        { token }
      )
      localStorage.setItem(KEY_REPORT_GENERATED, 'true')
      setReportGenerated(true)
      window.location.href = `/report/${result.report_id}`
    } catch {
      setReportError(true)
      setReportLoading(false)
    }
  }, [eligibilityData, isAuthenticated, token, showAuthGate])

  const handleQuizCta = useCallback(() => {
    if (!isAuthenticated) {
      showAuthGate('quiz')
      return
    }
    router.push('/quiz')
  }, [isAuthenticated, showAuthGate, router])

  // Resume report action after auth completion (save resume is handled by useSavedCourses hook)
  const resumeHandledRef = useRef(false)
  useEffect(() => {
    if (!token || resumeHandledRef.current) return
    const resumeStr = localStorage.getItem(KEY_RESUME_ACTION)
    if (!resumeStr) return

    try {
      const { action } = JSON.parse(resumeStr)
      if (action === 'save') return // handled by useSavedCourses hook
      localStorage.removeItem(KEY_RESUME_ACTION)
      resumeHandledRef.current = true

      if (action === 'loadmore') {
        setDisplayCount(prev => prev + COURSE_PAGE_SIZE)
      } else if (action === 'report' && eligibilityData) {
        setReportLoading(true)
        generateReport(eligibilityData.eligible_courses, eligibilityData.insights, 'bm', { token })
          .then(result => {
            localStorage.setItem(KEY_REPORT_GENERATED, 'true')
            setReportGenerated(true)
            window.location.href = `/report/${result.report_id}`
          })
          .catch(() => { setReportError(true); setReportLoading(false) })
      }
    } catch {
      // Ignore malformed resume action
    }
  }, [token, eligibilityData])

  // Redirect to onboarding if guard resolves with no grades
  useEffect(() => {
    if (guardLoading) return
    if (needsNric) {
      showAuthGate('profile')
    } else if (!onboarded) {
      router.replace('/onboarding/exam-type')
    }
  }, [guardLoading, onboarded, needsNric, showAuthGate, router])

  if (isLoading || guardLoading) {
    return <LoadingScreen />
  }

  if (!profile) {
    // ⚠ TWO DIFFERENT THINGS, and telling them apart is the whole of request #11. A student who
    // declared STPM and has not entered those results HAS onboarded — the guard above just proved
    // it, or they would have been redirected — so "complete the onboarding" is the one instruction
    // that cannot help them. Ask for the results that are actually missing.
    const pending = stpmPending || onboarded
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-ground-900 mb-4">
            {t(pending ? 'dashboard.stpmResultsPending' : 'dashboard.noProfile')}
          </h1>
          <p className="text-ground-600 mb-6">
            {t(pending ? 'dashboard.stpmResultsPendingDesc' : 'dashboard.noProfileDesc')}
          </p>
          <Link href={pending ? '/onboarding/stpm-grades' : '/onboarding/exam-type'} className="btn-primary">
            {t(pending ? 'dashboard.addStpmResults' : 'dashboard.startOnboarding')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-ground-50">
      <AppHeader />

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        {/* B40 application status — renders only when shortlisted/accepted */}
        <ScholarshipBanner />

        {/* STPM Results */}
        {examType === 'stpm' && (
          <>
            {isLoading ? (
              <div className="text-center py-12">
                <p className="text-ground-500">{t('common.loading')}</p>
              </div>
            ) : !stpmData ? (
              // Unreachable while `examType === 'stpm'` implies a resolved STPM cache — kept as a
              // backstop, but asking for the RESULTS, never for onboarding they have done.
              <div className="text-center py-12">
                <h2 className="text-xl font-semibold text-ground-900 mb-2">{t('dashboard.stpmResultsPending')}</h2>
                <p className="text-ground-500 mb-4">{t('dashboard.stpmResultsPendingDesc')}</p>
                <Link href="/onboarding/stpm-grades" className="btn-primary">
                  {t('dashboard.addStpmResults')}
                </Link>
              </div>
            ) : stpmResults === null ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-brand-shape border-t-transparent mb-4" />
                <p className="text-ground-500">{t('dashboard.checkingEligibility')}</p>
              </div>
            ) : stpmResults.length === 0 ? (
              <div className="text-center py-12">
                <h2 className="text-xl font-semibold text-ground-900 mb-2">{t('stpm.noResults')}</h2>
                <p className="text-ground-500 mb-4">{t('stpm.noResultsDesc')}</p>
                <Link href="/onboarding/stpm-grades" className="btn-primary">
                  {t('dashboard.editProfile')}
                </Link>
              </div>
            ) : (
              <StpmDashboardCards
                stpmResults={stpmResults}
                stpmData={stpmData}
                displayCount={displayCount}
                setDisplayCount={setDisplayCount}
                savedIds={savedIds}
                onToggleSave={handleSaveOrGate}
                quizSignals={quizSignals}
                framing={stpmFraming}
                onQuizCta={() => {
                  if (!isAuthenticated) { showAuthGate('quiz'); return }
                  router.push('/stpm/quiz')
                }}
                onLoadMoreGate={() => {
                  if (!isAuthenticated) { showAuthGate('loadmore'); return true }
                  return false
                }}
              />
            )}
          </>
        )}

        {/* Compact Dashboard Header */}
        {examType === 'spm' && eligibilityData && (
          <div className="bg-ground-0 rounded-xl border border-ground-200 px-4 sm:px-6 py-4 mb-6">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
              {/* Left: headline + chance pills */}
              <div>
                <h1 className="text-lg sm:text-xl font-bold text-ground-900">
                  {t('dashboard.qualifyFor')} <span className="text-primary-600">{eligibilityData.eligible_courses.length}</span> {t('dashboard.qualifyCourses')}
                </h1>
                {eligibilityData.insights && (
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-sm">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-positive-500" />
                      <span className="text-ground-600">{eligibilityData.insights.merit_summary.high} {t('dashboard.meritHigh')}</span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-caution-400" />
                      <span className="text-ground-600">{eligibilityData.insights.merit_summary.fair} {t('dashboard.meritFair')}</span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-critical-500" />
                      <span className="text-ground-600">{eligibilityData.insights.merit_summary.low} {t('dashboard.meritLow')}</span>
                    </span>
                    {eligibilityData.insights.merit_summary.no_data > 0 && (
                      <span className="text-ground-400">&middot; {eligibilityData.insights.merit_summary.no_data} unrated</span>
                    )}
                    <Link href="/onboarding/grades" className="text-xs text-ground-400 hover:text-primary-600 underline">
                      {t('dashboard.editProfile')}
                    </Link>
                  </div>
                )}
              </div>

              {/* Right: action buttons */}
              <div className="flex flex-wrap items-center gap-2">
                {existingReportId && (
                  <Link href={`/report/${existingReportId}`} className="btn-secondary text-sm whitespace-nowrap">
                    {t('dashboard.readReport')}
                  </Link>
                )}
                {quizSignals && !reportGenerated && (
                  <button
                    onClick={handleGenerateReport}
                    disabled={reportLoading}
                    className="btn-secondary text-sm whitespace-nowrap disabled:opacity-50"
                  >
                    {reportLoading ? t('dashboard.generating') : t('dashboard.generateReport')}
                  </button>
                )}
                {quizSignals ? (
                  <button onClick={handleRetakeQuiz} className="text-sm text-ground-400 hover:text-primary-600 underline whitespace-nowrap">
                    {t('dashboard.retakeQuiz')}
                  </button>
                ) : (
                  <button onClick={handleQuizCta} className="btn-primary text-sm whitespace-nowrap">
                    {t('dashboard.takeQuiz')}
                  </button>
                )}
              </div>
            </div>
            {reportError && <p className="text-critical-500 text-xs mt-2">{t('dashboard.reportError')}</p>}
          </div>
        )}

        {/* Pathway Cards — clickable filter pills */}
        {examType === 'spm' && pathwaySummaries.length > 0 && !eligibilityLoading && (
          <PathwayCards
            pathways={pathwaySummaries}
            activeFilter={filter}
            onFilterChange={(type) => {
              setFilter(type)
              setDisplayCount(COURSE_PAGE_SIZE)
            }}
          />
        )}

        {/* Loading State */}
        {examType === 'spm' && (eligibilityLoading || rankingLoading) && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-brand-shape border-t-transparent mb-4" />
            <p className="text-ground-600">
              {rankingLoading ? t('dashboard.rankingCourses') : t('dashboard.checkingEligibility')}
            </p>
          </div>
        )}

        {/* Error State */}
        {examType === 'spm' && error && (
          <div className="bg-critical-50 border border-critical-200 rounded-xl p-6 text-center">
            <p className="text-critical-600 mb-4">
              {t('dashboard.failedToLoad')}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="btn-primary"
            >
              {t('common.retry')}
            </button>
          </div>
        )}


        {/* Ranked Results — when quiz is completed */}
        {examType === 'spm' && rankingData && <RankedResults
          rankingData={rankingData}
          filter={filter}
          displayCount={displayCount}
          setDisplayCount={setDisplayCount}
          savedIds={savedIds}
          onToggleSave={handleSaveOrGate}
          onLoadMoreGate={() => {
            if (!isAuthenticated) { showAuthGate('loadmore'); return true }
            return false
          }}
        />}

        {/* Flat Course List — when no quiz taken */}
        {examType === 'spm' && eligibilityData && !quizSignals && !eligibilityLoading && (() => {
          // All courses (including Matric/STPM) come from the backend now
          // Backend already sorts by: merit label → credential → pathway → cutoff → name
          const allCourses = eligibilityData.eligible_courses

          const filteredCourses = filter === 'all'
            ? allCourses
            : allCourses.filter((c: { pathway_type?: string; source_type: string }) =>
                (c.pathway_type || c.source_type) === filter
              )
          const displayedCourses = filteredCourses.slice(0, displayCount)
          const remaining = filteredCourses.length - displayCount

          return (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {displayedCourses.map((course) => (
                  <CourseCard
                    key={course.course_id}
                    course={course}
                    isSaved={savedIds.has(course.course_id)}
                    onToggleSave={handleSaveOrGate}
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
                      setDisplayCount(displayCount + COURSE_PAGE_SIZE)
                    }}
                  >
                    {t('dashboard.loadMore')} ({remaining} {t('dashboard.remaining')})
                  </button>
                </div>
              )}
            </div>
          )
        })()}
      </div>

      <AppFooter />
    </main>
  )
}

// --- STPM Dashboard Cards (using CourseCard) ---

function StpmDashboardCards({
  stpmResults,
  stpmData,
  displayCount,
  setDisplayCount,
  savedIds,
  onToggleSave,
  quizSignals,
  framing,
  onQuizCta,
  onLoadMoreGate,
}: {
  stpmResults: StpmRankedCourse[]
  stpmData: { cgpa: number }
  displayCount: number
  setDisplayCount: (n: number | ((prev: number) => number)) => void
  savedIds: Set<string>
  onToggleSave?: (courseId: string) => void
  quizSignals: Record<string, Record<string, number>> | null
  framing?: StpmResultFraming | null
  onQuizCta: () => void
  onLoadMoreGate?: () => boolean
}) {
  const { t } = useT()
  const studentMerit = Math.round((stpmData.cgpa / 4.0) * 10000) / 100

  // Map StpmRankedCourse → EligibleCourse and sort
  const sortedCourses = useMemo(() => {
    const mapped = stpmResults.map(prog => {
      const level = getMeritLevel(studentMerit, prog.merit_score)
      const gap = prog.merit_score != null ? prog.merit_score - studentMerit : null
      const meritLabel = level === 'high' ? 'High' : level === 'fair' ? 'Fair' : level === 'low' ? 'Low' : null
      const meritColor = level === 'high' ? 'green' : level === 'fair' ? 'amber' : level === 'low' ? 'red' : null

      const course: EligibleCourse = {
        course_id: prog.course_id,
        course_name: prog.course_name,
        level: 'Ijazah Sarjana Muda',
        field: '', // Legacy — CourseCard uses field_key via useFieldTaxonomy
        field_key: prog.field_key || '',
        source_type: 'ua',
        qualification: 'STPM' as const,
        merit_cutoff: prog.merit_score,
        student_merit: studentMerit,
        merit_label: meritLabel,
        merit_color: meritColor,
      }
      return { course, level, gap, university: prog.university }
    })

    // Separate by merit level
    const high = mapped.filter(m => m.level === 'high')
    const fair = mapped.filter(m => m.level === 'fair')
    const low = mapped.filter(m => m.level === 'low')
    const noRating = mapped.filter(m => m.level === 'none')

    // Sort high: highest merit score descending
    high.sort((a, b) => (b.course.merit_cutoff ?? 0) - (a.course.merit_cutoff ?? 0))

    // Sort fair: smallest gap first (ascending)
    fair.sort((a, b) => Math.abs(a.gap ?? 0) - Math.abs(b.gap ?? 0))

    // Sort low: smallest gap first (ascending)
    low.sort((a, b) => Math.abs(a.gap ?? 0) - Math.abs(b.gap ?? 0))

    // Insert no-rating in the middle of fair
    const midFair = Math.floor(fair.length / 2)
    const fairWithNoRating = [...fair.slice(0, midFair), ...noRating, ...fair.slice(midFair)]

    return [...high, ...fairWithNoRating, ...low]
  }, [stpmResults, studentMerit])

  const highCount = sortedCourses.filter(m => m.level === 'high').length
  const fairCount = sortedCourses.filter(m => m.level === 'fair').length
  const lowCount = sortedCourses.filter(m => m.level === 'low').length

  const displayed = sortedCourses.slice(0, displayCount)
  const remaining = sortedCourses.length - displayCount

  return (
    <div>
      {/* Header */}
      <div className="bg-ground-0 rounded-xl border border-ground-200 px-6 py-4 mb-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            {framing && quizSignals ? (
              <>
                <h1 className="text-xl font-bold text-ground-900">{framing.heading}</h1>
                <p className="text-sm text-ground-500 mt-0.5">{framing.subtitle}</p>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm">
                  <span className="text-ground-600">{stpmResults.length} {t('dashboard.qualifyCourses')}</span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-positive-500" />
                    <span className="text-ground-600">{highCount} {t('dashboard.meritHigh')}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-caution-400" />
                    <span className="text-ground-600">{fairCount} {t('dashboard.meritFair')}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-critical-500" />
                    <span className="text-ground-600">{lowCount} {t('dashboard.meritLow')}</span>
                  </span>
                </div>
              </>
            ) : (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <h1 className="text-xl font-bold text-ground-900">
                  {t('dashboard.qualifyFor')} <span className="text-primary-600">{stpmResults.length}</span> {t('dashboard.qualifyCourses')}
                </h1>
                <div className="flex items-center gap-3 text-sm">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-positive-500" />
                    <span className="text-ground-600">{highCount} {t('dashboard.meritHigh')}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-caution-400" />
                    <span className="text-ground-600">{fairCount} {t('dashboard.meritFair')}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-critical-500" />
                    <span className="text-ground-600">{lowCount} {t('dashboard.meritLow')}</span>
                  </span>
                </div>
              </div>
            )}
            <Link href="/onboarding/stpm-grades" className="text-xs text-ground-400 hover:text-primary-600 underline mt-1 inline-block">
              {t('dashboard.editProfile')}
            </Link>
          </div>
          <div className="flex items-center gap-2">
            {quizSignals ? (
              <button onClick={onQuizCta} className="text-sm text-ground-400 hover:text-primary-600 underline whitespace-nowrap">
                {t('stpmQuiz.retakeQuiz')}
              </button>
            ) : (
              <button onClick={onQuizCta} className="btn-primary text-sm whitespace-nowrap">
                {t('stpmQuiz.takeQuiz')}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Course Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {displayed.map(({ course, university }) => (
          <CourseCard
            key={course.course_id}
            course={course}
            isSaved={savedIds.has(course.course_id)}
            onToggleSave={onToggleSave}
            institutionName={university}
          />
        ))}
      </div>

      {remaining > 0 && (
        <div className="text-center py-4">
          <button
            className="btn-secondary"
            onClick={() => {
              if (onLoadMoreGate?.()) return
              setDisplayCount((prev: number) => prev + COURSE_PAGE_SIZE)
            }}
          >
            {t('dashboard.loadMore')} ({remaining} {t('dashboard.remaining')})
          </button>
        </div>
      )}
    </div>
  )
}

// --- Ranked Results Section ---

function RankedResults({
  rankingData,
  filter,
  displayCount,
  setDisplayCount,
  savedIds,
  onToggleSave,
  onLoadMoreGate,
}: {
  rankingData: RankingResult
  filter: string
  displayCount: number
  setDisplayCount: (n: number) => void
  savedIds: Set<string>
  onToggleSave?: (courseId: string) => void
  onLoadMoreGate?: () => boolean
}) {
  const { t } = useT()

  const filtered = filter === 'all'
    ? rankingData.ranked
    : rankingData.ranked.filter(c => (c.pathway_type || c.source_type) === filter)

  const displayed = filtered.slice(0, displayCount)
  const remaining = filtered.length - displayCount

  return (
    <div>
      {displayed.length > 0 && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {displayed.map((course, idx) => (
              <CourseCard
                key={course.course_id}
                course={course}
                rank={idx < 3 ? idx + 1 : undefined}
                isSaved={savedIds.has(course.course_id)}
                onToggleSave={onToggleSave}
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
                  if (onLoadMoreGate?.()) return
                  setDisplayCount(displayCount + COURSE_PAGE_SIZE)
                }}
              >
                {t('dashboard.loadMore')} ({remaining} {t('dashboard.remaining')})
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// --- Small Components ---

function LoadingScreen() {
  const { t } = useT()
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-ground-0">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-brand-shape border-t-transparent mb-4" />
        <p className="text-ground-600">{t('common.loadingProfile')}</p>
      </div>
    </div>
  )
}

