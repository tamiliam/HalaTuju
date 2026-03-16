'use client'

import Link from 'next/link'
import type { EligibleCourse, RankedCourse } from '@/lib/api'
import { TYPE_LABELS, TYPE_COLORS, LEVEL_COLORS } from '@/lib/courseBadges'
import { useFieldTaxonomy } from '@/hooks/useFieldTaxonomy'

/** Build the detail page URL for a course. */
function getCourseHref(courseId: string, sourceType?: string, qualification?: string): string {
  if (qualification === 'STPM') {
    return `/stpm/${courseId}`
  }
  return `/course/${courseId}`
}

function isRankedCourse(course: EligibleCourse | RankedCourse): course is RankedCourse {
  return 'fit_score' in course
}

interface CourseCardProps {
  course: EligibleCourse | RankedCourse
  rank?: number
  isSaved: boolean
  onToggleSave?: (courseId: string) => void
  institutionName?: string
  institutionState?: string
  institutionCount?: number
}

export default function CourseCard({ course, rank, isSaved, onToggleSave, institutionName, institutionState, institutionCount }: CourseCardProps) {
  const { getImageUrl, getFieldName } = useFieldTaxonomy()
  const imageUrl = getImageUrl(course.field_key)
  const fieldLabel = getFieldName(course.field_key) || 'View course details'
  const isLowMerit = course.merit_label === 'Low'

  return (
    <div
      className={`bg-white rounded-xl border overflow-hidden transition-all flex flex-col ${
        rank
          ? 'border-2 border-primary-100 hover:border-primary-300'
          : 'border-gray-200 hover:border-primary-300'
      } hover:shadow-sm ${isLowMerit ? 'opacity-60' : ''}`}
    >
      {/* Field image header */}
      <div className="relative h-36 bg-gray-100 flex-shrink-0">
        <img
          src={imageUrl}
          alt={fieldLabel}
          className="w-full h-full object-cover"
        />

        {/* Rank badge overlay */}
        {rank && (
          <div className="absolute top-2 left-2 w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center shadow">
            <span className="text-white text-sm font-bold">#{rank}</span>
          </div>
        )}

        {/* Save button overlay — not for pathway entries */}
        {onToggleSave && !course.course_id.startsWith('pathway-') && (
          <button
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              onToggleSave(course.course_id)
            }}
            className="absolute top-2 right-2 p-1.5 bg-white/80 backdrop-blur-sm rounded-full hover:bg-white transition-colors"
            aria-label={isSaved ? 'Remove from saved' : 'Save course'}
          >
            <svg
              className={`w-4 h-4 ${isSaved ? 'text-primary-500 fill-primary-500' : 'text-gray-500'}`}
              viewBox="0 0 24 24"
              fill={isSaved ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Card body */}
      <Link href={getCourseHref(course.course_id, course.source_type, course.qualification)} className="flex-1 p-4 flex flex-col">
        {/* Type + Level badges */}
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              TYPE_COLORS[course.pathway_type || course.source_type] || 'bg-gray-100 text-gray-700'
            }`}
          >
            {TYPE_LABELS[course.pathway_type || course.source_type] || course.source_type}
          </span>
          {course.level && (
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                LEVEL_COLORS[course.level] || 'bg-gray-50 text-gray-600'
              }`}
            >
              {course.level}
            </span>
          )}
        </div>

        {/* Course name */}
        <h3 className="text-sm font-semibold text-gray-900 mb-1 line-clamp-2">
          {course.course_name || course.course_id}
        </h3>

        {/* Field */}
        <div className="flex items-center gap-1 text-xs text-gray-500 mb-1">
          <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
          </svg>
          <span className="truncate">{fieldLabel}</span>
        </div>

        {/* Institution info (search context only) */}
        {institutionName && (
          <div className="flex items-center gap-1 text-xs text-gray-500 mb-1">
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
            </svg>
            <span className="truncate">
              {institutionName}
              {institutionState && <span className="text-gray-400"> ({institutionState})</span>}
              {(institutionCount ?? 0) > 1 && (
                <span className="text-gray-400 ml-1">+{(institutionCount ?? 1) - 1}</span>
              )}
            </span>
          </div>
        )}

        {/* Merit score indicator */}
        <MeritIndicator
          label={course.merit_label}
          studentMerit={course.student_merit}
          meritCutoff={course.merit_cutoff}
          displayStudent={course.merit_display_student}
          displayCutoff={course.merit_display_cutoff}
        />

        {/* Fit reasons (ranked courses only) */}
        {isRankedCourse(course) && course.fit_reasons && course.fit_reasons.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {course.fit_reasons.slice(0, 2).map((reason, i) => (
              <span
                key={i}
                className="inline-block px-2 py-0.5 bg-primary-50 text-primary-700 text-xs rounded-full"
              >
                {reason}
              </span>
            ))}
          </div>
        )}
      </Link>
    </div>
  )
}

function MeritIndicator({
  label,
  studentMerit,
  meritCutoff,
  displayStudent,
  displayCutoff,
}: {
  label: string | null
  studentMerit: number | null
  meritCutoff: number | null
  displayStudent?: string
  displayCutoff?: string
}) {
  if (!label) return null

  const hasScores = studentMerit !== null && meritCutoff !== null

  const barColor =
    label === 'High' ? 'bg-green-500' :
    label === 'Fair' ? 'bg-amber-400' :
    'bg-red-500'

  const textClass =
    label === 'High' ? 'text-green-700' :
    label === 'Fair' ? 'text-amber-700' :
    'text-red-700'

  const displayLabel =
    label === 'High' ? 'High Chance' :
    label === 'Fair' ? 'Fair Chance' :
    'Low Chance'

  // Fallback: simple dot + label when numeric scores are unavailable
  if (!hasScores) {
    return (
      <div className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full inline-block flex-shrink-0 ${barColor}`} />
        <span className={`text-xs font-medium ${textClass}`}>{displayLabel}</span>
      </div>
    )
  }

  const fillWidth = Math.min(Math.max(studentMerit, 0), 100)
  const cutoffPos = Math.min(Math.max(meritCutoff, 0), 100)

  return (
    <div className="mt-1">
      {/* Bar track */}
      <div className="relative h-3 bg-gray-100 rounded-full mb-1">
        {/* Student score fill */}
        <div
          className={`h-full rounded-full relative ${barColor}`}
          style={{ width: `${fillWidth}%` }}
        >
          {fillWidth >= 12 && (
            <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[9px] font-bold text-white leading-none">
              {displayStudent ?? studentMerit}
            </span>
          )}
        </div>
        {/* Cutoff dashed zone */}
        <div
          className="absolute top-0 h-full border-l-2 border-dashed border-gray-400"
          style={{ left: `${cutoffPos}%` }}
        />
      </div>
      {/* Label row */}
      <div className="flex items-center justify-between">
        <span className={`text-[11px] font-semibold ${textClass}`}>{displayLabel}</span>
        <span className="text-[10px] text-gray-400">
          You: {displayStudent ?? studentMerit} &nbsp;|&nbsp; Need: {displayCutoff ?? meritCutoff}
        </span>
      </div>
    </div>
  )
}
