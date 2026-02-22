'use client'

import { useEffect, useState, useCallback } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import {
  checkEligibility,
  getSavedCourses,
  saveCourse,
  unsaveCourse,
  getRankedResults,
  generateReport,
  type StudentProfile,
  type RankedCourse,
  type RankingResult,
  type Insights,
} from '@/lib/api'
import { getSession } from '@/lib/supabase'
import CourseCard from '@/components/CourseCard'
import { useT } from '@/lib/i18n'
import LanguageSelector from '@/components/LanguageSelector'

export default function DashboardPage() {
  const { t } = useT()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')
  const [displayCount, setDisplayCount] = useState(20)
  const [token, setToken] = useState<string | null>(null)
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())
  const [quizSignals, setQuizSignals] = useState<Record<string, Record<string, number>> | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState(false)

  // Load profile from localStorage + check auth session on mount
  useEffect(() => {
    const grades = localStorage.getItem('halatuju_grades')
    const profileData = localStorage.getItem('halatuju_profile')

    if (grades && profileData) {
      const parsedGrades = JSON.parse(grades)
      const parsedProfile = JSON.parse(profileData)

      setProfile({
        grades: parsedGrades,
        gender: parsedProfile.gender,
        nationality: parsedProfile.nationality,
        colorblind: parsedProfile.colorblind || false,
        disability: parsedProfile.disability || false,
      })
    }

    // Check for quiz signals
    const signals = localStorage.getItem('halatuju_quiz_signals')
    if (signals) {
      setQuizSignals(JSON.parse(signals))
    }

    setIsLoading(false)

    // Check for Supabase session and load saved courses
    getSession().then(({ session }) => {
      if (session?.access_token) {
        setToken(session.access_token)
        getSavedCourses({ token: session.access_token })
          .then(({ saved_courses }) => {
            setSavedIds(new Set(saved_courses.map(c => c.course_id)))
          })
          .catch(() => {}) // Silently fail — saved state is non-critical
      }
    }).catch(() => {})
  }, [])

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

  const handleRetakeQuiz = () => {
    localStorage.removeItem('halatuju_quiz_signals')
    localStorage.removeItem('halatuju_signal_strength')
    setQuizSignals(null)
  }

  const handleGenerateReport = async () => {
    if (!token || !eligibilityData) return
    setReportLoading(true)
    setReportError(false)
    try {
      const result = await generateReport(
        eligibilityData.eligible_courses,
        eligibilityData.insights,
        'bm',
        { token }
      )
      window.location.href = `/report/${result.report_id}`
    } catch {
      setReportError(true)
      setReportLoading(false)
    }
  }

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
          <Link href="/onboarding/stream" className="btn-primary">
            {t('dashboard.startOnboarding')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Image src="/logo-icon.png" alt="HalaTuju" width={60} height={32} />
          </Link>
          <div className="flex items-center gap-4">
            <LanguageSelector />
            <Link href="/saved" className="text-gray-600 hover:text-gray-900">
              {t('common.saved')}
            </Link>
            <Link href="/settings" className="text-gray-600 hover:text-gray-900">
              {t('common.settings')}
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        {/* Summary Card */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                {t('dashboard.title')}
              </h1>
              <p className="text-gray-600">
                {quizSignals
                  ? t('dashboard.rankedSubtitle')
                  : t('dashboard.subtitle')}
              </p>
            </div>
            <div className="flex gap-2">
              <Link
                href="/onboarding/grades"
                className="btn-secondary whitespace-nowrap"
              >
                {t('dashboard.editProfile')}
              </Link>
            </div>
          </div>

          {/* Stats */}
          {eligibilityData && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mt-6 pt-6 border-t">
              <StatCard
                number={eligibilityData.eligible_courses.length}
                label={t('dashboard.totalEligible')}
              />
              <StatCard
                number={eligibilityData.stats.poly || 0}
                label={t('dashboard.polytechnic')}
              />
              <StatCard
                number={eligibilityData.stats.kkom || 0}
                label={t('dashboard.kolej')}
              />
              <StatCard
                number={eligibilityData.stats.tvet || 0}
                label={t('dashboard.tvet')}
              />
              <StatCard
                number={eligibilityData.stats.ua || 0}
                label={t('dashboard.university')}
              />
              <StatCard
                number={eligibilityData.stats.pismp || 0}
                label={t('dashboard.teacherTraining')}
              />
            </div>
          )}
        </div>

        {/* Insights Panel */}
        {eligibilityData?.insights && (
          <InsightsPanel insights={eligibilityData.insights} />
        )}

        {/* Generate Report CTA — show when logged in and eligibility loaded */}
        {eligibilityData && token && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-1">
                  {t('dashboard.reportTitle')}
                </h2>
                <p className="text-gray-600 text-sm">
                  {t('dashboard.reportDesc')}
                </p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <button
                  onClick={handleGenerateReport}
                  disabled={reportLoading}
                  className="btn-primary whitespace-nowrap"
                >
                  {reportLoading ? t('dashboard.generating') : t('dashboard.generateReport')}
                </button>
                {reportError && (
                  <p className="text-red-500 text-sm">{t('dashboard.reportError')}</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Quiz CTA — show when no quiz taken yet */}
        {eligibilityData && !quizSignals && (
          <div className="bg-gradient-to-r from-primary-500 to-primary-600 rounded-xl p-6 mb-8 text-white">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold mb-1">
                  {t('dashboard.quizTitle')}
                </h2>
                <p className="text-primary-100 text-sm">
                  {t('dashboard.quizDesc')}
                </p>
              </div>
              <Link
                href="/quiz"
                className="bg-white text-primary-600 px-6 py-3 rounded-lg font-medium hover:bg-primary-50 transition-colors whitespace-nowrap text-center"
              >
                {t('dashboard.takeQuiz')}
              </Link>
            </div>
          </div>
        )}

        {/* Quiz completed banner */}
        {quizSignals && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-8 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span className="text-green-800 text-sm font-medium">
                {t('dashboard.quizDone')}
              </span>
            </div>
            <button
              onClick={handleRetakeQuiz}
              className="text-green-600 hover:text-green-800 text-sm underline"
            >
              {t('dashboard.retakeQuiz')}
            </button>
          </div>
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
        {rankingData && <RankedResults
          rankingData={rankingData}
          filter={filter}
          setFilter={setFilter}
          displayCount={displayCount}
          setDisplayCount={setDisplayCount}
          savedIds={savedIds}
          onToggleSave={token ? handleToggleSave : undefined}
        />}

        {/* Flat Course List — when no quiz taken */}
        {eligibilityData && !quizSignals && !eligibilityLoading && (() => {
          const filteredCourses = filter === 'all'
            ? eligibilityData.eligible_courses
            : eligibilityData.eligible_courses.filter(c => c.source_type === filter)
          const displayedCourses = filteredCourses.slice(0, displayCount)
          const remaining = filteredCourses.length - displayCount

          return (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">
                  {t('dashboard.eligibleCourses')} ({filteredCourses.length})
                </h2>
                <FilterDropdown filter={filter} setFilter={setFilter} setDisplayCount={setDisplayCount} />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {displayedCourses.map((course) => (
                  <CourseCard
                    key={course.course_id}
                    course={course}
                    isSaved={savedIds.has(course.course_id)}
                    onToggleSave={token ? handleToggleSave : undefined}
                  />
                ))}
              </div>

              {remaining > 0 && (
                <div className="text-center py-4">
                  <button
                    className="btn-secondary"
                    onClick={() => setDisplayCount(displayCount + 20)}
                  >
                    {t('dashboard.loadMore')} ({remaining} {t('dashboard.remaining')})
                  </button>
                </div>
              )}
            </div>
          )
        })()}
      </div>
    </main>
  )
}

// --- Ranked Results Section ---

function RankedResults({
  rankingData,
  filter,
  setFilter,
  displayCount,
  setDisplayCount,
  savedIds,
  onToggleSave,
}: {
  rankingData: RankingResult
  filter: string
  setFilter: (f: string) => void
  displayCount: number
  setDisplayCount: (n: number) => void
  savedIds: Set<string>
  onToggleSave?: (courseId: string) => void
}) {
  const { t } = useT()
  const filterCourses = (courses: RankedCourse[]) =>
    filter === 'all' ? courses : courses.filter(c => c.source_type === filter)

  const filteredTop5 = filterCourses(rankingData.top_5)
  const filteredRest = filterCourses(rankingData.rest)
  const displayedRest = filteredRest.slice(0, displayCount)
  const remaining = filteredRest.length - displayCount

  return (
    <div className="space-y-8">
      {/* Filter */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          {t('dashboard.rankedCourses')} ({rankingData.total_ranked})
        </h2>
        <FilterDropdown filter={filter} setFilter={setFilter} setDisplayCount={setDisplayCount} />
      </div>

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
                onClick={() => setDisplayCount(displayCount + 20)}
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

function StatCard({ number, label }: { number: number; label: string }) {
  return (
    <div className="text-center">
      <div className="text-3xl font-bold text-primary-500">{number}</div>
      <div className="text-sm text-gray-600">{label}</div>
    </div>
  )
}

function InsightsPanel({ insights }: { insights: Insights }) {
  const { t } = useT()
  const meritTotal = insights.merit_summary.high + insights.merit_summary.fair + insights.merit_summary.low

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 mb-8">
      {/* Summary */}
      <p className="text-gray-700 mb-6">{insights.summary_text}</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Top Fields */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            {t('dashboard.insightsTopFields')}
          </h3>
          <ul className="space-y-2">
            {insights.top_fields.map((f) => (
              <li key={f.field} className="flex justify-between text-sm">
                <span className="text-gray-700 truncate mr-2">{f.field}</span>
                <span className="text-gray-500 font-medium whitespace-nowrap">{f.count} {t('dashboard.courses')}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Level Distribution */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            {t('dashboard.insightsLevels')}
          </h3>
          <ul className="space-y-2">
            {insights.level_distribution.map((l) => (
              <li key={l.level} className="flex justify-between text-sm">
                <span className="text-gray-700 truncate mr-2">{l.level}</span>
                <span className="text-gray-500 font-medium whitespace-nowrap">{l.count}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Merit Summary */}
        {meritTotal > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              {t('dashboard.insightsMerit')}
            </h3>
            <div className="space-y-2">
              <MeritBar label={t('dashboard.meritHigh')} count={insights.merit_summary.high} total={meritTotal} color="bg-green-500" />
              <MeritBar label={t('dashboard.meritFair')} count={insights.merit_summary.fair} total={meritTotal} color="bg-yellow-500" />
              <MeritBar label={t('dashboard.meritLow')} count={insights.merit_summary.low} total={meritTotal} color="bg-red-500" />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function MeritBar({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-20 text-gray-600">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-gray-500 w-8 text-right">{count}</span>
    </div>
  )
}

function FilterDropdown({
  filter,
  setFilter,
  setDisplayCount,
}: {
  filter: string
  setFilter: (f: string) => void
  setDisplayCount: (n: number) => void
}) {
  const { t } = useT()
  return (
    <select
      className="input w-auto"
      value={filter}
      onChange={(e) => {
        setFilter(e.target.value)
        setDisplayCount(20)
      }}
    >
      <option value="all">{t('dashboard.allTypes')}</option>
      <option value="poly">{t('dashboard.polytechnic')}</option>
      <option value="kkom">{t('dashboard.kolej')}</option>
      <option value="tvet">{t('dashboard.tvet')}</option>
      <option value="ua">{t('dashboard.university')}</option>
      <option value="pismp">{t('dashboard.teacherTraining')}</option>
    </select>
  )
}
