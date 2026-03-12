'use client'

import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import {
  checkEligibility,
  checkStpmEligibility,
  rankStpmProgrammes,
  getSavedCourses,
  saveCourse,
  unsaveCourse,
  getRankedResults,
  generateReport,
  getReports,
  type StudentProfile,
  type EligibleCourse,
  type RankedCourse,
  type RankingResult,
  type StpmEligibleProgramme,
  type StpmRankedProgramme,
} from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import CourseCard from '@/components/CourseCard'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'
import PathwayCards, { type PathwaySummary } from '@/components/PathwayCards'

const RESUME_ACTION_KEY = 'halatuju_resume_action'

export default function DashboardPage() {
  const { t } = useT()
  const router = useRouter()
  const { isAuthenticated, token, showAuthGate } = useAuth()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')
  const [displayCount, setDisplayCount] = useState(6)
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())
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
  const [stpmResults, setStpmResults] = useState<StpmRankedProgramme[] | null>(null)

  // Load profile from localStorage on mount
  useEffect(() => {
    const examTypeStr = localStorage.getItem('halatuju_exam_type') || 'spm'
    setExamType(examTypeStr as 'spm' | 'stpm')

    if (examTypeStr === 'stpm') {
      // Load STPM-specific data
      const stpmGradesStr = localStorage.getItem('halatuju_stpm_grades')
      const stpmCgpaStr = localStorage.getItem('halatuju_stpm_cgpa')
      const muetBandStr = localStorage.getItem('halatuju_muet_band')
      const spmPrereqStr = localStorage.getItem('halatuju_spm_prereq')
      const profileData = localStorage.getItem('halatuju_profile')

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
      const grades = localStorage.getItem('halatuju_grades')
      const profileData = localStorage.getItem('halatuju_profile')

      if (grades && profileData) {
        const parsedGrades = JSON.parse(grades)
        const parsedProfile = JSON.parse(profileData)
        const savedMerit = localStorage.getItem('halatuju_merit')

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

      const signals = localStorage.getItem('halatuju_quiz_signals')
      if (signals) {
        setQuizSignals(JSON.parse(signals))
      }

      setReportGenerated(localStorage.getItem('halatuju_report_generated') === 'true')
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
      const signalsStr = localStorage.getItem('halatuju_quiz_signals')
      const signals = signalsStr ? JSON.parse(signalsStr) : {}
      return rankStpmProgrammes({
        eligible_programmes: data.eligible_programmes,
        student_cgpa: stpmData.cgpa,
        student_signals: signals,
      })
    }).then(ranked => {
      setStpmResults(ranked.ranked_programmes)
    }).catch(err => {
      console.error('STPM eligibility/ranking failed:', err)
    })
  }, [examType, stpmData, profile])

  // Load saved courses when token becomes available
  useEffect(() => {
    if (token) {
      getSavedCourses({ token })
        .then(({ saved_courses }) => {
          setSavedIds(new Set(saved_courses.map(c => c.course_id)))
        })
        .catch(() => {})
    }
  }, [token])

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

  const handleToggleSave = useCallback(async (courseId: string) => {
    if (!token) return
    const isSaved = savedIds.has(courseId)

    // Optimistic update
    setSavedIds(prev => {
      const next = new Set(prev)
      if (isSaved) next.delete(courseId)
      else next.add(courseId)
      return next
    })

    try {
      if (isSaved) {
        await unsaveCourse(courseId, { token })
      } else {
        await saveCourse(courseId, { token })
      }
    } catch {
      // Revert on failure
      setSavedIds(prev => {
        const next = new Set(prev)
        if (isSaved) next.add(courseId)
        else next.delete(courseId)
        return next
      })
    }
  }, [token, savedIds])

  // Save handler that gates on auth
  const handleSaveOrGate = useCallback((courseId: string) => {
    if (!isAuthenticated) {
      showAuthGate('save', { courseId })
      return
    }
    handleToggleSave(courseId)
  }, [isAuthenticated, showAuthGate, handleToggleSave])

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

    // Fixed order: Asasi, Matriculation, Form 6 first, then the rest
    const orderedPathways: { type: PathwaySummary['type']; count: number }[] = [
      { type: 'asasi', count: courseCounts['asasi'] || 0 },
      { type: 'matric', count: courseCounts['matric'] || 0 },
      { type: 'stpm', count: courseCounts['stpm'] || 0 },
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
      localStorage.setItem('halatuju_report_generated', 'true')
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

  // Resume actions after auth completion (from auth gate modal)
  const resumeHandledRef = useRef(false)
  useEffect(() => {
    if (!token || resumeHandledRef.current) return
    const resumeStr = localStorage.getItem(RESUME_ACTION_KEY)
    if (!resumeStr) return
    localStorage.removeItem(RESUME_ACTION_KEY)
    resumeHandledRef.current = true

    try {
      const { action, courseId } = JSON.parse(resumeStr)
      if (action === 'save' && courseId) {
        setSavedIds(prev => { const n = new Set(prev); n.add(courseId); return n })
        saveCourse(courseId, { token }).catch(() => {
          setSavedIds(prev => {
            const n = new Set(prev)
            n.delete(courseId)
            return n
          })
        })
      } else if (action === 'report' && eligibilityData) {
        setReportLoading(true)
        generateReport(eligibilityData.eligible_courses, eligibilityData.insights, 'bm', { token })
          .then(result => {
            localStorage.setItem('halatuju_report_generated', 'true')
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
            ) : (
              <div>
                <div className="mb-6">
                  <h2 className="text-2xl font-bold text-gray-900">
                    {t('dashboard.qualifyFor')} <span className="text-primary-500">{stpmResults.length}</span> degree programmes
                  </h2>
                  <Link href="/onboarding/exam-type" className="text-xs text-gray-400 hover:text-primary-500 underline mt-1 inline-block">
                    {t('dashboard.editProfile')}
                  </Link>
                  <Link href="/stpm/search" className="text-xs text-primary-500 hover:text-primary-600 underline ml-3">
                    {t('stpm.browseAll')}
                  </Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {stpmResults.slice(0, displayCount).map(prog => (
                    <div key={prog.program_id} className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-5">
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="font-semibold text-gray-900 text-sm line-clamp-2 flex-1 mr-2">{prog.program_name}</h3>
                        <span className={`shrink-0 px-2 py-0.5 text-xs font-bold rounded-full ${
                          prog.fit_score >= 70 ? 'bg-green-100 text-green-800' :
                          prog.fit_score >= 55 ? 'bg-amber-100 text-amber-800' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          Fit: {Math.round(prog.fit_score)}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mb-1">{prog.university}</p>
                      {prog.fit_reasons && prog.fit_reasons.length > 0 && (
                        <p className="text-xs text-gray-400 mb-3">{prog.fit_reasons.join(' · ')}</p>
                      )}
                      <div className="flex flex-wrap gap-1.5">
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full">
                          CGPA ≥ {prog.min_cgpa.toFixed(2)}
                        </span>
                        <span className="px-2 py-0.5 bg-green-50 text-green-700 text-xs rounded-full">
                          MUET ≥ Band {prog.min_muet_band}
                        </span>
                        {prog.req_interview && (
                          <span className="px-2 py-0.5 bg-amber-50 text-amber-700 text-xs rounded-full">
                            Interview
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                {stpmResults.length > displayCount && (
                  <button
                    onClick={() => setDisplayCount(prev => prev + 6)}
                    className="mt-4 w-full py-3 text-primary-600 hover:text-primary-700 text-sm font-medium"
                  >
                    {t('dashboard.loadMore')} ({stpmResults.length - displayCount} {t('dashboard.remaining')})
                  </button>
                )}
              </div>
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

