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
import { useT } from '@/lib/i18n'
import PathwayCards, { type PathwaySummary } from '@/components/PathwayCards'
import { useToast } from '@/components/Toast'
import { KEY_RESUME_ACTION, KEY_EXAM_TYPE, KEY_STPM_GRADES, KEY_STPM_CGPA, KEY_MUET_BAND, KEY_SPM_PREREQ, KEY_PROFILE, KEY_GRADES, KEY_MERIT, KEY_QUIZ_SIGNALS, KEY_REPORT_GENERATED } from '@/lib/storage'

function getMeritLevel(studentMerit: number, courseMerit: number | null | undefined): 'high' | 'fair' | 'low' | 'none' {
  if (courseMerit === null || courseMerit === undefined) return 'none'
  if (studentMerit >= courseMerit) return 'high'
  if (studentMerit >= courseMerit - 5) return 'fair'
  return 'low'
}

const MERIT_STYLES = {
  high: 'bg-green-100 text-green-800',
  fair: 'bg-amber-100 text-amber-800',
  low: 'bg-red-100 text-red-800',
  none: 'bg-gray-100 text-gray-600',
}
const MERIT_LABELS = { high: 'High', fair: 'Fair', low: 'Low', none: '—' }

export default function DashboardPage() {
  const { t } = useT()
  const router = useRouter()
  const { isAuthenticated, token, showAuthGate } = useAuth()
  const { savedIds, toggleSave: handleSaveOrGate } = useSavedCourses()
  const { showToast } = useToast()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')
  const [displayCount, setDisplayCount] = useState(6)
  const [quizSignals, setQuizSignals] = useState<Record<string, Record<string, number>> | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState(false)
  const [existingReportId, setExistingReportId] = useState<number | null>(null)
  const [reportGenerated, setReportGenerated] = useState(false)
  const [examType, setExamType] = useState<'spm' | 'stpm'>('spm')
  const [stpmData, setStpmData] = useState<{
    stpmGrades: Record<string, string>
    cgpa: number
    muetBand: number
    spmGrades: Record<string, string>
  } | null>(null)
  const [stpmResults, setStpmResults] = useState<StpmRankedCourse[] | null>(null)

  // Load profile from localStorage on mount
  useEffect(() => {
    const examTypeStr = localStorage.getItem(KEY_EXAM_TYPE) || 'spm'
    setExamType(examTypeStr as 'spm' | 'stpm')

    if (examTypeStr === 'stpm') {
      // Load STPM-specific data
      const stpmGradesStr = localStorage.getItem(KEY_STPM_GRADES)
      const stpmCgpaStr = localStorage.getItem(KEY_STPM_CGPA)
      const muetBandStr = localStorage.getItem(KEY_MUET_BAND)
      const spmPrereqStr = localStorage.getItem(KEY_SPM_PREREQ)
      const profileData = localStorage.getItem(KEY_PROFILE)

      if (stpmGradesStr && stpmCgpaStr && muetBandStr) {
        const parsedProfile = profileData ? JSON.parse(profileData) : {}
        setProfile({
          grades: {},
          gender: parsedProfile.gender || 'male',
          nationality: parsedProfile.nationality || 'malaysian',
          colorblind: parsedProfile.colorblind || false,
          disability: parsedProfile.disability || false,
        })
        setStpmData({
          stpmGrades: JSON.parse(stpmGradesStr),
          cgpa: parseFloat(stpmCgpaStr),
          muetBand: parseInt(muetBandStr),
          spmGrades: spmPrereqStr ? JSON.parse(spmPrereqStr) : {},
        })
      }
      setIsLoading(false)
    } else {
      // Existing SPM logic
      const grades = localStorage.getItem(KEY_GRADES)
      const profileData = localStorage.getItem(KEY_PROFILE)

      if (grades && profileData) {
        const parsedGrades = JSON.parse(grades)
        const parsedProfile = JSON.parse(profileData)
        const savedMerit = localStorage.getItem(KEY_MERIT)

        setProfile({
          grades: parsedGrades,
          gender: parsedProfile.gender,
          nationality: parsedProfile.nationality,
          colorblind: parsedProfile.colorblind || false,
          disability: parsedProfile.disability || false,
          coq_score: parsedProfile.coqScore ?? 5.0,
          ...(savedMerit && { student_merit: parseFloat(savedMerit) }),
        })
      }

      const signals = localStorage.getItem(KEY_QUIZ_SIGNALS)
      if (signals) {
        setQuizSignals(JSON.parse(signals))
      }

      setReportGenerated(localStorage.getItem(KEY_REPORT_GENERATED) === 'true')
      setIsLoading(false)
    }
  }, [])

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
      colorblind: profile.colorblind ? 'Ya' : 'Tidak',
    }).then(data => {
      // Chain ranking after eligibility
      const signalsStr = localStorage.getItem(KEY_QUIZ_SIGNALS)
      const signals = signalsStr ? JSON.parse(signalsStr) : {}
      return rankStpmCourses({
        eligible_courses: data.eligible_courses,
        student_cgpa: stpmData.cgpa,
        student_signals: signals,
      })
    }).then(ranked => {
      setStpmResults(ranked.ranked_courses)
    }).catch(err => {
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

      if (action === 'report' && eligibilityData) {
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

  if (isLoading) {
    return <LoadingScreen />
  }

  if (!profile) {
    return (
      <div className="min-h-screen flex items-center justify-center">
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
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        {/* STPM Results */}
        {examType === 'stpm' && (
          <>
            {isLoading ? (
              <div className="text-center py-12">
                <p className="text-gray-500">{t('common.loading')}</p>
              </div>
            ) : !stpmData ? (
              <div className="text-center py-12">
                <h2 className="text-xl font-semibold text-gray-900 mb-2">{t('dashboard.noProfile')}</h2>
                <p className="text-gray-500 mb-4">{t('dashboard.noProfileDesc')}</p>
                <Link href="/onboarding/exam-type" className="btn-primary">
                  {t('dashboard.startOnboarding')}
                </Link>
              </div>
            ) : stpmResults === null ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
                <p className="text-gray-500">{t('dashboard.checkingEligibility')}</p>
              </div>
            ) : stpmResults.length === 0 ? (
              <div className="text-center py-12">
                <h2 className="text-xl font-semibold text-gray-900 mb-2">{t('stpm.noResults')}</h2>
                <p className="text-gray-500 mb-4">{t('stpm.noResultsDesc')}</p>
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
                onQuizCta={handleQuizCta}
              />
            )}
          </>
        )}

        {/* Compact Dashboard Header */}
        {examType === 'spm' && eligibilityData && (
          <div className="bg-white rounded-xl border border-gray-200 px-6 py-4 mb-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              {/* Left: headline + chance pills */}
              <div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <h1 className="text-xl font-bold text-gray-900">
                    {t('dashboard.qualifyFor')} <span className="text-primary-500">{eligibilityData.eligible_courses.length}</span> {t('dashboard.qualifyCourses')}
                  </h1>
                  {eligibilityData.insights && (
                    <div className="flex items-center gap-3 text-sm">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-green-500" />
                        <span className="text-gray-600">{eligibilityData.insights.merit_summary.high} {t('dashboard.meritHigh')}</span>
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-amber-400" />
                        <span className="text-gray-600">{eligibilityData.insights.merit_summary.fair} {t('dashboard.meritFair')}</span>
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-red-500" />
                        <span className="text-gray-600">{eligibilityData.insights.merit_summary.low} {t('dashboard.meritLow')}</span>
                      </span>
                      {eligibilityData.insights.merit_summary.no_data > 0 && (
                        <span className="text-gray-400">&middot; {eligibilityData.insights.merit_summary.no_data} unrated</span>
                      )}
                    </div>
                  )}
                </div>
                <Link href="/onboarding/grades" className="text-xs text-gray-400 hover:text-primary-500 underline mt-1 inline-block">
                  {t('dashboard.editProfile')}
                </Link>
              </div>

              {/* Right: action buttons */}
              <div className="flex items-center gap-2">
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
                  <button onClick={handleRetakeQuiz} className="text-sm text-gray-400 hover:text-primary-500 underline whitespace-nowrap">
                    {t('dashboard.retakeQuiz')}
                  </button>
                ) : (
                  <button onClick={handleQuizCta} className="btn-primary text-sm whitespace-nowrap">
                    {t('dashboard.takeQuiz')}
                  </button>
                )}
              </div>
            </div>
            {reportError && <p className="text-red-500 text-xs mt-2">{t('dashboard.reportError')}</p>}
          </div>
        )}

        {/* Pathway Cards — clickable filter pills */}
        {examType === 'spm' && pathwaySummaries.length > 0 && !eligibilityLoading && (
          <PathwayCards
            pathways={pathwaySummaries}
            activeFilter={filter}
            onFilterChange={(type) => { setFilter(type); setDisplayCount(20) }}
          />
        )}

        {/* Loading State */}
        {examType === 'spm' && (eligibilityLoading || rankingLoading) && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
            <p className="text-gray-600">
              {rankingLoading ? t('dashboard.rankingCourses') : t('dashboard.checkingEligibility')}
            </p>
          </div>
        )}

        {/* Error State */}
        {examType === 'spm' && error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <p className="text-red-600 mb-4">
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
                    onClick={() => setDisplayCount(displayCount + 6)}
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
  onQuizCta,
}: {
  stpmResults: StpmRankedCourse[]
  stpmData: { cgpa: number }
  displayCount: number
  setDisplayCount: (n: number | ((prev: number) => number)) => void
  savedIds: Set<string>
  onToggleSave?: (courseId: string) => void
  quizSignals: Record<string, Record<string, number>> | null
  onQuizCta: () => void
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
        field: prog.field || '',
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
      <div className="bg-white rounded-xl border border-gray-200 px-6 py-4 mb-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <h1 className="text-xl font-bold text-gray-900">
                {t('dashboard.qualifyFor')} <span className="text-primary-500">{stpmResults.length}</span> {t('dashboard.qualifyCourses')}
              </h1>
              <div className="flex items-center gap-3 text-sm">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-gray-600">{highCount} {t('dashboard.meritHigh')}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  <span className="text-gray-600">{fairCount} {t('dashboard.meritFair')}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  <span className="text-gray-600">{lowCount} {t('dashboard.meritLow')}</span>
                </span>
              </div>
            </div>
            <Link href="/onboarding/stpm-grades" className="text-xs text-gray-400 hover:text-primary-500 underline mt-1 inline-block">
              {t('dashboard.editProfile')}
            </Link>
          </div>
          <div className="flex items-center gap-2">
            {!quizSignals && (
              <button onClick={onQuizCta} className="btn-primary text-sm whitespace-nowrap">
                {t('dashboard.takeQuiz')}
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
            onClick={() => setDisplayCount((prev: number) => prev + 6)}
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
}: {
  rankingData: RankingResult
  filter: string
  displayCount: number
  setDisplayCount: (n: number) => void
  savedIds: Set<string>
  onToggleSave?: (courseId: string) => void
}) {
  const { t } = useT()
  const filterCourses = (courses: RankedCourse[]) =>
    filter === 'all'
      ? courses
      : courses.filter(c => (c.pathway_type || c.source_type) === filter)

  const filteredTop5 = filterCourses(rankingData.top_5)
  const filteredRest = filterCourses(rankingData.rest)
  const displayedRest = filteredRest.slice(0, displayCount)
  const remaining = filteredRest.length - displayCount

  return (
    <div className="space-y-8">
      {/* Top 5 */}
      {filteredTop5.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-primary-600 uppercase tracking-wide mb-3">
            {t('dashboard.topMatches')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredTop5.map((course, idx) => (
              <CourseCard
                key={course.course_id}
                course={course}
                rank={idx + 1}
                isSaved={savedIds.has(course.course_id)}
                onToggleSave={onToggleSave}
                institutionName={course.institution_name}
                institutionState={course.institution_state}
                institutionCount={course.institution_count}
              />
            ))}
          </div>
        </div>
      )}

      {/* Rest */}
      {displayedRest.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            {t('dashboard.otherEligible')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {displayedRest.map((course) => (
              <CourseCard
                key={course.course_id}
                course={course}
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
                onClick={() => setDisplayCount(displayCount + 6)}
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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-white">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mb-4" />
        <p className="text-gray-600">{t('common.loadingProfile')}</p>
      </div>
    </div>
  )
}

