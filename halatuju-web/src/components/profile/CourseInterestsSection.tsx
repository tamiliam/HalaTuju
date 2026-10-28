'use client'

/**
 * /profile Section 6, "My Course Interests": the student's saved courses, each with its interest
 * status and a remove button. MOVED here verbatim from `src/app/profile/page.tsx` (2026-10-28) to
 * bring the page under its size budget — the same markup, the same calls, the same toasts.
 */
import type { Dispatch, SetStateAction } from 'react'
import Link from 'next/link'
import { updateSavedCourseStatus, unsaveCourse } from '@/lib/api'
import type { SavedCourseWithStatus } from '@/lib/api'
import { useToast } from '@/components/ToastContext'
import { useT } from '@/lib/i18n'

const STATUS_OPTIONS = [
  { value: 'interested', label: 'profile.status.interested', color: 'bg-ground-100 text-ground-600' },
  { value: 'planning', label: 'profile.status.planning', color: 'bg-info-100 text-info-700' },
  { value: 'applied', label: 'profile.status.applied', color: 'bg-caution-100 text-caution-700' },
  { value: 'got_offer', label: 'profile.status.got_offer', color: 'bg-positive-100 text-positive-700' },
]

export default function CourseInterestsSection({ savedCourses, setSavedCourses, token }: {
  savedCourses: SavedCourseWithStatus[]
  setSavedCourses: Dispatch<SetStateAction<SavedCourseWithStatus[]>>
  token: string | null
}) {
  const { t } = useT()
  const { showToast } = useToast()

  const handleStatusChange = async (courseId: string, newStatus: string) => {
    if (!token) return
    try {
      await updateSavedCourseStatus(courseId, newStatus, { token })
      setSavedCourses(prev =>
        prev.map(c => c.course_id === courseId ? { ...c, interest_status: newStatus } : c)
      )
    } catch (err) {
      showToast('Failed to update course status.', 'error')
    }
  }

  const handleRemoveCourse = async (courseId: string) => {
    if (!token) return
    try {
      await unsaveCourse(courseId, { token })
      setSavedCourses(prev => prev.filter(c => c.course_id !== courseId))
    } catch (err) {
      showToast('Failed to remove course.', 'error')
    }
  }

  const getStatusColor = (status: string) =>
    STATUS_OPTIONS.find(s => s.value === status)?.color || 'bg-ground-100 text-ground-600'

  return (
          <div className="bg-ground-0 border border-ground-100 rounded-xl shadow-sm p-6 mb-5">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-brand-fill to-brand-fill-hover flex items-center justify-center shadow-sm shadow-primary-500/20">
                <svg className="w-5 h-5 text-brand-fill-ink" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-ground-900">{t('profile.courseInterests')}</h2>
              {savedCourses.length > 0 && (
                <span className="px-2 py-0.5 bg-ground-100 text-ground-500 text-xs font-medium rounded-full">
                  {savedCourses.length}
                </span>
              )}
            </div>

            {savedCourses.length === 0 ? (
              <p className="text-sm text-ground-400 py-4 text-center">{t('profile.noCourses')}</p>
            ) : (
              <div className="divide-y divide-ground-100">
                {savedCourses.map(course => (
                  <div key={course.course_id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="flex-1 min-w-0">
                      <Link
                        href={`/course/${course.course_id}`}
                        className="text-sm font-medium text-ground-900 hover:text-primary-600 truncate block"
                      >
                        {course.course}
                      </Link>
                      <p className="text-xs text-ground-400 truncate">{course.level}</p>
                    </div>
                    <select
                      value={course.interest_status}
                      onChange={e => handleStatusChange(course.course_id, e.target.value)}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium border-0 cursor-pointer ${getStatusColor(course.interest_status)}`}
                    >
                      {STATUS_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{t(opt.label)}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleRemoveCourse(course.course_id)}
                      className="p-1 text-ground-300 hover:text-critical-600 transition-colors"
                      title="Remove"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
  )
}
