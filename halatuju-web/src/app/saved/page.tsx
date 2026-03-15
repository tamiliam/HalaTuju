'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { getSavedCourses, unsaveCourse, updateSavedCourseStatus, type SavedCourseWithStatus } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useToast } from '@/components/Toast'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

type QualificationTab = 'SPM' | 'STPM'

export default function SavedPage() {
  const { t } = useT()
  const { token, isAuthenticated, isLoading: authLoading } = useAuth()
  const { showToast } = useToast()
  const [courses, setCourses] = useState<SavedCourseWithStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<QualificationTab>('SPM')
  const [updatingId, setUpdatingId] = useState<string | null>(null)

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

  const filteredCourses = courses.filter(c =>
    (c.course_type === 'stpm' ? 'STPM' : 'SPM') === activeTab
  )

  const spmCount = courses.filter(c => c.course_type !== 'stpm').length
  const stpmCount = courses.filter(c => c.course_type === 'stpm').length

  const handleRemove = async (courseId: string) => {
    if (!token) return
    setCourses(prev => prev.filter(c => c.course_id !== courseId))
    try {
      await unsaveCourse(courseId, { token })
      showToast('Course removed', 'success')
    } catch {
      const { saved_courses } = await getSavedCourses({ token })
      setCourses(saved_courses)
      showToast('Failed to remove course', 'error')
    }
  }

  const handleStatusUpdate = async (courseId: string, newStatus: string) => {
    if (!token) return
    setUpdatingId(courseId)

    // Toggle logic:
    // - Un-toggle 'got_offer' → fall back to 'applied' (you still applied)
    // - Un-toggle 'applied' → fall back to 'interested'
    const course = courses.find(c => c.course_id === courseId)
    let targetStatus = newStatus
    if (course?.interest_status === newStatus) {
      targetStatus = newStatus === 'got_offer' ? 'applied' : 'interested'
    }

    // Optimistic update
    setCourses(prev => prev.map(c =>
      c.course_id === courseId ? { ...c, interest_status: targetStatus } : c
    ))

    try {
      await updateSavedCourseStatus(courseId, targetStatus, { token })
    } catch {
      // Revert on failure
      setCourses(prev => prev.map(c =>
        c.course_id === courseId ? { ...c, interest_status: course?.interest_status || 'interested' } : c
      ))
      showToast('Failed to update status', 'error')
    }
    setUpdatingId(null)
  }

  /** Returns the correct detail page path based on course type */
  const detailHref = (course: SavedCourseWithStatus) =>
    course.course_type === 'stpm'
      ? `/stpm/${course.course_id}`
      : `/course/${course.course_id}`

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

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

        {!loading && isAuthenticated && courses.length > 0 && (
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

            {/* SPM / STPM tabs */}
            <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
              <button
                onClick={() => setActiveTab('SPM')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'SPM'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                SPM ({spmCount})
              </button>
              <button
                onClick={() => setActiveTab('STPM')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'STPM'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                STPM ({stpmCount})
              </button>
            </div>

            {/* Course list */}
            {filteredCourses.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500">
                  {activeTab === 'STPM'
                    ? t('saved.noStpm')
                    : t('saved.noSpm')}
                </p>
              </div>
            ) : (
              <div className="grid gap-4">
                {filteredCourses.map(course => {
                  const isApplied = course.interest_status === 'applied' || course.interest_status === 'got_offer'
                  const hasOffer = course.interest_status === 'got_offer'

                  return (
                    <div key={course.course_id} className="bg-white rounded-xl border border-gray-200 p-5">
                      <div className="flex items-start justify-between">
                        <Link href={detailHref(course)} className="flex-1">
                          <h3 className="font-semibold text-gray-900">{course.course || course.course_id}</h3>
                          <p className="text-sm text-gray-500 mt-0.5">
                            {course.institution_name && (
                              <>{course.institution_name} &middot; </>
                            )}
                            {course.level} &middot; {course.field}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5 font-mono">{course.course_id}</p>
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

                      {/* Status buttons — both always visible, toggle on/off */}
                      <div className="mt-3 flex gap-2">
                        <button
                          onClick={() => handleStatusUpdate(course.course_id, 'applied')}
                          disabled={updatingId === course.course_id}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors disabled:opacity-50 ${
                            isApplied
                              ? 'bg-primary-100 text-primary-700 border border-primary-300'
                              : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          {isApplied && (
                            <svg className="w-3.5 h-3.5 inline mr-1 -mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                          )}
                          {t('outcomes.iApplied')}
                        </button>
                        <button
                          onClick={() => handleStatusUpdate(course.course_id, 'got_offer')}
                          disabled={updatingId === course.course_id}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors disabled:opacity-50 ${
                            hasOffer
                              ? 'bg-green-100 text-green-700 border border-green-300'
                              : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          {hasOffer && (
                            <svg className="w-3.5 h-3.5 inline mr-1 -mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                          )}
                          {t('outcomes.iGotOffer')}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </div>

      <AppFooter />
    </main>
  )
}
