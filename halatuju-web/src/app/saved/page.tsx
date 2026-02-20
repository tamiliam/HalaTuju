'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { getSavedCourses, unsaveCourse, type Course } from '@/lib/api'
import { getSession } from '@/lib/supabase'
import { useT } from '@/lib/i18n'

export default function SavedPage() {
  const { t } = useT()
  const [token, setToken] = useState<string | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSession().then(({ session }) => {
      if (session?.access_token) {
        setToken(session.access_token)
        getSavedCourses({ token: session.access_token })
          .then(({ saved_courses }) => setCourses(saved_courses))
          .catch(() => {})
          .finally(() => setLoading(false))
      } else {
        setLoading(false)
      }
    }).catch(() => setLoading(false))
  }, [])

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

        {!loading && !token && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">{t('saved.signInPrompt')}</p>
            <Link href="/login" className="btn-primary">{t('saved.signIn')}</Link>
          </div>
        )}

        {!loading && token && courses.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">{t('saved.empty')}</p>
            <Link href="/dashboard" className="btn-primary">{t('saved.browseCourses')}</Link>
          </div>
        )}

        {!loading && courses.length > 0 && (
          <div className="grid gap-4">
            {courses.map(course => (
              <div key={course.course_id} className="bg-white rounded-xl border border-gray-200 p-5 flex items-center justify-between">
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
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
