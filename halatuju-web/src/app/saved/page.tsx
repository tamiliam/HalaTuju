'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { getSavedCourses, unsaveCourse, createOutcome, type Course } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'

export default function SavedPage() {
  const { t } = useT()
  const { token, isAuthenticated, isLoading: authLoading } = useAuth()
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [appliedIds, setAppliedIds] = useState<Set<string>>(new Set())
  const [applyingId, setApplyingId] = useState<string | null>(null)

  useEffect(() => {
    if (authLoading) return
    if (!isAuthenticated || !token) {
      setLoading(false)
      return
    }
    getSavedCourses({ token })
      .then(({ saved_courses }) => setCourses(saved_courses))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [authLoading, isAuthenticated, token])

  const handleRemove = async (courseId: string) => {
    if (!token) return
    setCourses(prev => prev.filter(c => c.course_id !== courseId))
    try {
      await unsaveCourse(courseId, { token })
    } catch {
      const { saved_courses } = await getSavedCourses({ token })
      setCourses(saved_courses)
    }
  }

  const handleApplied = async (courseId: string) => {
    if (!token) return
    setApplyingId(courseId)
    try {
      await createOutcome({ course_id: courseId, status: 'applied' }, { token })
      const n = new Set(appliedIds)
      n.add(courseId)
      setAppliedIds(n)
    } catch {
      // Might already exist (409) — treat as success
      const n = new Set(appliedIds)
      n.add(courseId)
      setAppliedIds(n)
    }
    setApplyingId(null)
  }

  const handleGotOffer = async (courseId: string) => {
    if (!token) return
    setApplyingId(courseId)
    try {
      await createOutcome({ course_id: courseId, status: 'offered' }, { token })
      const n = new Set(appliedIds)
      n.add(courseId)
      setAppliedIds(n)
    } catch {
      const n = new Set(appliedIds)
      n.add(courseId)
      setAppliedIds(n)
    }
    setApplyingId(null)
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">{t('saved.title')}</h1>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8">
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          </div>
        )}

        {!loading && !isAuthenticated && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">{t('saved.signInPrompt')}</p>
            <Link href="/login" className="btn-primary">{t('saved.signIn')}</Link>
          </div>
        )}

        {!loading && isAuthenticated && courses.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">{t('saved.empty')}</p>
            <Link href="/dashboard" className="btn-primary">{t('saved.browseCourses')}</Link>
          </div>
        )}

        {!loading && courses.length > 0 && (
          <>
            {/* Track applications CTA */}
            <Link
              href="/outcomes"
              className="block mb-6 bg-primary-50 border border-primary-200 rounded-xl p-4 hover:bg-primary-100 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold text-primary-900">{t('outcomes.trackApplications')}</h3>
                  <p className="text-sm text-primary-700">{t('outcomes.trackApplicationsDesc')}</p>
                </div>
              </div>
            </Link>

            <div className="grid gap-4">
              {courses.map(course => (
                <div key={course.course_id} className="bg-white rounded-xl border border-gray-200 p-5">
                  <div className="flex items-center justify-between">
                    <Link href={`/course/${course.course_id}`} className="flex-1">
                      <h3 className="font-semibold text-gray-900">{course.course || course.course_id}</h3>
                      <p className="text-sm text-gray-500">{course.level} &middot; {course.field}</p>
                    </Link>
                    <button
                      onClick={() => handleRemove(course.course_id)}
                      className="ml-4 p-2 text-gray-400 hover:text-red-500 transition-colors"
                      aria-label={t('saved.remove')}
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  {/* Outcome action buttons */}
                  <div className="mt-3 flex gap-2">
                    {appliedIds.has(course.course_id) ? (
                      <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-green-50 text-green-700 text-sm font-medium">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                        {t('outcomes.statusApplied')}
                      </span>
                    ) : (
                      <>
                        <button
                          onClick={() => handleApplied(course.course_id)}
                          disabled={applyingId === course.course_id}
                          className="px-3 py-1.5 rounded-full border border-primary-300 text-primary-700 text-sm font-medium hover:bg-primary-50 transition-colors disabled:opacity-50"
                        >
                          {t('outcomes.iApplied')}
                        </button>
                        <button
                          onClick={() => handleGotOffer(course.course_id)}
                          disabled={applyingId === course.course_id}
                          className="px-3 py-1.5 rounded-full border border-green-300 text-green-700 text-sm font-medium hover:bg-green-50 transition-colors disabled:opacity-50"
                        >
                          {t('outcomes.iGotOffer')}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  )
}
