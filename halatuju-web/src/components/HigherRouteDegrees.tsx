'use client'

/**
 * THE COURSE GUIDE FOR A MATRICULATION / ASASI / DIPLOMA HOLDER — browse only (ruling D2, third
 * results route S2b, 2026-10-26).
 *
 * HalaTuju holds no entry rules for these qualifications (the ePanduan scrape knows only the SPM
 * and STPM tracks), and an honest eligibility verdict cannot be made from a CGPA against STPM
 * requirements. So this lists EVERY degree programme (`/stpm/search/`, the course search's own
 * list), says plainly why, and shows NO High / Fair / Low merit band — a band would be a verdict
 * we cannot back. Each card links to the programme's own page, where its requirements are.
 */
import { useEffect, useState } from 'react'
import Link from 'next/link'
import CourseCard from '@/components/CourseCard'
import { searchStpmCourses, type EligibleCourse } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { resultsEditPath, type ThirdRouteKind } from '@/lib/qualification'
import { COURSE_PAGE_SIZE } from '@/lib/storage'

export default function HigherRouteDegrees({ kind, savedIds, onToggleSave, onLoadMoreGate }: {
  kind: ThirdRouteKind
  savedIds: Set<string>
  onToggleSave?: (courseId: string) => void
  onLoadMoreGate?: () => boolean
}) {
  const { t } = useT()
  const [courses, setCourses] = useState<{ course: EligibleCourse; university: string }[] | null>(null)
  const [shown, setShown] = useState(COURSE_PAGE_SIZE)

  useEffect(() => {
    let live = true
    searchStpmCourses({})
      .then((r) => {
        if (!live) return
        setCourses(r.courses.map((c) => ({
          university: c.university,
          course: {
            course_id: c.course_id, course_name: c.course_name, level: 'Ijazah Sarjana Muda',
            field: '', field_key: c.field_key || '', source_type: 'ua', qualification: 'STPM',
            // ⚠ NO MERIT: no figure, no band (D2) — the card then draws no High/Fair/Low chip.
            merit_cutoff: null, student_merit: null, merit_label: null, merit_color: null,
          },
        })))
      })
      .catch(() => { if (live) setCourses([]) })
    return () => { live = false }
  }, [])

  const remaining = (courses?.length ?? 0) - shown

  return (
    <div>
      <div className="bg-ground-0 rounded-xl border border-ground-200 px-6 py-4 mb-6">
        <h1 className="text-xl font-bold text-ground-900">
          {t('dashboard.higherBrowseTitle')}
          {courses && courses.length > 0 && <span className="text-primary-600"> ({courses.length})</span>}
        </h1>
        <p className="text-sm text-ground-500 mt-1">{t('dashboard.higherBrowseNote')}</p>
        <Link href={resultsEditPath(kind)} className="text-xs text-ground-400 hover:text-primary-600 underline mt-1 inline-block">
          {t('dashboard.editProfile')}
        </Link>
      </div>

      {courses === null ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-brand-shape border-t-transparent mb-4" />
          <p className="text-ground-500">{t('common.loading')}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {courses.slice(0, shown).map(({ course, university }) => (
            <CourseCard key={course.course_id} course={course} isSaved={savedIds.has(course.course_id)}
              onToggleSave={onToggleSave} institutionName={university} />
          ))}
        </div>
      )}

      {remaining > 0 && (
        <div className="text-center py-4">
          <button className="btn-secondary" onClick={() => {
            if (onLoadMoreGate?.()) return
            setShown((n) => n + COURSE_PAGE_SIZE)
          }}>
            {t('dashboard.loadMore')} ({remaining} {t('dashboard.remaining')})
          </button>
        </div>
      )}
    </div>
  )
}
