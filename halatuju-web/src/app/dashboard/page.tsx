'use client'

import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import {
  checkEligibility,
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
} from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import CourseCard from '@/components/CourseCard'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'
import { checkAllPathways, getPathwayFitScore } from '@/lib/pathways'
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

  // Load profile from localStorage on mount
  useEffect(() => {
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
  }, [])

  // Compute pathway eligibility from grades
  const pathwayResults = useMemo(() => {
    if (!profile) return []
    const coq = profile.coq_score ?? 0
    return checkAllPathways(profile.grades, coq)
  }, [profile])

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

  // Merge Matric/STPM into ranked results so they compete on score
  const mergedRankingData = useMemo((): RankingResult | undefined => {
    if (!rankingData) return undefined

    // Build synthetic ranked entries from eligible pathway results
    const syntheticEntries: RankedCourse[] = []
    if (pathwayResults) {
      for (const r of pathwayResults) {
        if (!r.eligible) continue
        let fitScore = getPathwayFitScore(r, quizSignals)
        const isMatric = r.pathway === 'matric'

        // Compute merit label for the chance indicator
        let meritLabel: string | null = null
        let studentMerit: number | null = null
        let meritCutoff: number | null = null
        let meritDisplayStudent: string | undefined
        let meritDisplayCutoff: string | undefined

        if (isMatric && r.merit !== undefined) {
          studentMerit = Math.round(r.merit * 10) / 10
          meritCutoff = 94 // High/Fair boundary as the "need" line
          meritLabel = r.merit >= 94 ? 'High' : r.merit >= 89 ? 'Fair' : 'Low'
        } else if (!isMatric && r.mataGred !== undefined) {
          // STPM: full range is 3 (best) to 27 (worst)
          // Invert to 0-100 scale: (27 - gred) / 24 * 100
          studentMerit = Math.round((27 - r.mataGred) / 24 * 100)
          // Display raw mata gred values (lower is better)
          meritDisplayStudent = `${r.mataGred}`
          if (r.trackId === 'sains') {
            // Science cutoff at 18: (27-18)/24*100 = 37.5%
            meritCutoff = Math.round((27 - 18) / 24 * 100)
            meritLabel = 'High'
            meritDisplayCutoff = '18'
          } else {
            // Social Science cutoff at 12: (27-12)/24*100 = 62.5%
            meritCutoff = Math.round((27 - 12) / 24 * 100)
            meritLabel = r.mataGred <= 12 ? 'High' : 'Fair'
            meritDisplayCutoff = '12'
          }
        }

        // Apply merit penalty (same as backend: Fair -5, Low -15)
        const MERIT_PENALTY: Record<string, number> = { High: 0, Fair: -5, Low: -15 }
        fitScore += MERIT_PENALTY[meritLabel || ''] ?? 0

        syntheticEntries.push({
          course_id: `pathway-${r.pathway}-${r.trackId}`,
          course_name: isMatric
            ? `Matriculation — ${r.trackName}`
            : `Form 6 (STPM) — ${r.trackName}`,
          level: 'Pre-University',
          field: isMatric ? 'Foundation Studies' : 'Form 6',
          source_type: r.pathway,
          pathway_type: r.pathway,
          merit_cutoff: meritCutoff,
          student_merit: studentMerit,
          merit_label: meritLabel,
          merit_color: null,
          merit_display_student: meritDisplayStudent,
          merit_display_cutoff: meritDisplayCutoff,
          fit_score: fitScore,
          fit_reasons: isMatric
            ? [`Matric merit: ${r.merit?.toFixed(1)}`]
            : [`Mata gred: ${r.mataGred}/${r.maxMataGred}`],
        })
      }
    }

    if (syntheticEntries.length === 0) return rankingData

    // Merge all courses, re-sort by fit_score desc, split into top 6 + rest
    const all = [...rankingData.top_5, ...rankingData.rest, ...syntheticEntries]
    all.sort((a, b) => b.fit_score - a.fit_score)

    return {
      top_5: all.slice(0, 6),
      rest: all.slice(6),
      total_ranked: all.length,
    }
  }, [rankingData, pathwayResults, quizSignals])

  // Build pathway summary badges from eligibility data + pathway engine
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

    // Matric/STPM counts from pathway engine
    let matricCount = 0
    let stpmCount = 0
    if (pathwayResults) {
      matricCount = pathwayResults.filter(r => r.pathway === 'matric' && r.eligible).length
      stpmCount = pathwayResults.filter(r => r.pathway === 'stpm' && r.eligible).length
    }

    // Fixed order: Asasi, Matriculation, Form 6 first, then the rest
    const orderedPathways: { type: PathwaySummary['type']; count: number }[] = [
      { type: 'asasi', count: courseCounts['asasi'] || 0 },
      { type: 'matric', count: matricCount },
      { type: 'stpm', count: stpmCount },
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
  }, [eligibilityData, pathwayResults, t])

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
        {/* Compact Dashboard Header */}
        {eligibilityData && (
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
        {pathwaySummaries.length > 0 && !eligibilityLoading && (
          <PathwayCards
            pathways={pathwaySummaries}
            activeFilter={filter}
            onFilterChange={(type) => { setFilter(type); setDisplayCount(20) }}
          />
        )}

        {/* Loading State */}
        {(eligibilityLoading || rankingLoading) && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
            <p className="text-gray-600">
              {rankingLoading ? t('dashboard.rankingCourses') : t('dashboard.checkingEligibility')}
            </p>
          </div>
        )}

        {/* Error State */}
        {error && (
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
        {mergedRankingData && <RankedResults
          rankingData={mergedRankingData}
          filter={filter}
          displayCount={displayCount}
          setDisplayCount={setDisplayCount}
          savedIds={savedIds}
          onToggleSave={handleSaveOrGate}
        />}

        {/* Flat Course List — when no quiz taken */}
        {eligibilityData && !quizSignals && !eligibilityLoading && (() => {
          // Inject synthetic Matric/STPM entries into the flat list
          const syntheticFlat: EligibleCourse[] = pathwayResults
            .filter(r => r.eligible)
            .map(r => {
              const isMatric = r.pathway === 'matric'

              let meritLabel: string | null = null
              let studentMerit: number | null = null
              let meritCutoff: number | null = null
              let meritDisplayStudent: string | undefined
              let meritDisplayCutoff: string | undefined

              if (isMatric && r.merit !== undefined) {
                studentMerit = Math.round(r.merit * 10) / 10
                meritCutoff = 94
                meritLabel = r.merit >= 94 ? 'High' : r.merit >= 89 ? 'Fair' : 'Low'
              } else if (!isMatric && r.mataGred !== undefined) {
                studentMerit = Math.round((27 - r.mataGred) / 24 * 100)
                meritDisplayStudent = `${r.mataGred}`
                if (r.trackId === 'sains') {
                  meritCutoff = Math.round((27 - 18) / 24 * 100)
                  meritLabel = 'High'
                  meritDisplayCutoff = '18'
                } else {
                  meritCutoff = Math.round((27 - 12) / 24 * 100)
                  meritLabel = r.mataGred <= 12 ? 'High' : 'Fair'
                  meritDisplayCutoff = '12'
                }
              }

              return {
                course_id: `pathway-${r.pathway}-${r.trackId}`,
                course_name: isMatric
                  ? `Matriculation — ${r.trackName}`
                  : `Form 6 (STPM) — ${r.trackName}`,
                level: 'Pre-University',
                field: isMatric ? 'Foundation Studies' : 'Form 6',
                source_type: r.pathway,
                pathway_type: r.pathway,
                merit_cutoff: meritCutoff,
                student_merit: studentMerit,
                merit_label: meritLabel,
                merit_color: null,
                merit_display_student: meritDisplayStudent,
                merit_display_cutoff: meritDisplayCutoff,
              }
            })

          // Sort all courses using the same logic as the backend:
          // 1. Merit label (High > Fair > Low > no data)
          // 2. Credential priority (Asasi/Pre-U > PISMP > Diploma > Sijil)
          // 3. Source type priority (asasi > matric > stpm > ua > pismp > poly > kkom > tvet)
          // 4. Merit cutoff (higher = more competitive, first)
          // 5. Name (alphabetical)
          const MERIT_LABEL_PRI: Record<string, number> = { High: 3, Fair: 2, Low: 1 }
          const PATHWAY_PRI: Record<string, number> = {
            asasi: 8, matric: 7, stpm: 6,
            pismp: 5, university: 4, poly: 3, kkom: 2, iljtm: 1, ilkbs: 1, tvet: 0,
          }

          function credentialPriority(name: string, sourceType: string): number {
            if (sourceType === 'pismp') return 4
            const lower = name.toLowerCase().trim()
            if (lower.startsWith('asasi') || lower.includes('foundation') || lower.startsWith('matriculation') || lower.startsWith('form 6')) return 5
            if (lower.startsWith('diploma')) return 3
            if (lower.includes('sijil lanjutan')) return 2
            if (lower.startsWith('sijil')) return 1
            return 0
          }

          const allCourses = [...syntheticFlat, ...eligibilityData.eligible_courses]
          allCourses.sort((a, b) => {
            // 1. Merit label: High first, then Fair, then Low, no data treated as Fair
            const ma = MERIT_LABEL_PRI[a.merit_label || ''] ?? 2
            const mb = MERIT_LABEL_PRI[b.merit_label || ''] ?? 2
            if (mb !== ma) return mb - ma

            // 2. Credential priority
            const ca = credentialPriority(a.course_name, a.source_type)
            const cb = credentialPriority(b.course_name, b.source_type)
            if (cb !== ca) return cb - ca

            // 3. Pathway/source type priority
            const pta = (a as { pathway_type?: string }).pathway_type || a.source_type
            const ptb = (b as { pathway_type?: string }).pathway_type || b.source_type
            const pa = PATHWAY_PRI[pta] ?? 0
            const pb = PATHWAY_PRI[ptb] ?? 0
            if (pb !== pa) return pb - pa

            // 4. Merit cutoff (more competitive first)
            const cutDiff = (b.merit_cutoff ?? 0) - (a.merit_cutoff ?? 0)
            if (cutDiff !== 0) return cutDiff

            // 5. Name
            return a.course_name.localeCompare(b.course_name)
          })

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

