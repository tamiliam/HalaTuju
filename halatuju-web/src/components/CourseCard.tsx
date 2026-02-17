'use client'

import Link from 'next/link'
import type { EligibleCourse, RankedCourse } from '@/lib/api'

const SUPABASE_STORAGE = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images'

const FIELD_IMAGE_SLUGS: Record<string, string> = {
  'Mekanikal & Automotif': 'mekanikal-automotif',
  'Perniagaan & Perdagangan': 'perniagaan-perdagangan',
  'Elektrik & Elektronik': 'elektrik-elektronik',
  'Pertanian & Bio-Industri': 'pertanian-bio-industri',
  'Sivil, Seni Bina & Pembinaan': 'sivil-senibina-pembinaan',
  'Hospitaliti, Kulinari & Pelancongan': 'hospitaliti-kulinari-pelancongan',
  'Komputer, IT & Multimedia': 'komputer-it-multimedia',
  'Aero, Marin, Minyak & Gas': 'aero-marin-minyakgas',
  'Seni Reka & Kreatif': 'senireka-kreatif',
}

function getFieldImageUrl(field: string): string | null {
  const slug = FIELD_IMAGE_SLUGS[field]
  return slug ? `${SUPABASE_STORAGE}/${slug}.png` : null
}

const TYPE_LABELS: Record<string, string> = {
  poly: 'Polytechnic',
  tvet: 'TVET',
  ua: 'University',
}

const TYPE_COLORS: Record<string, string> = {
  poly: 'bg-blue-100 text-blue-700',
  tvet: 'bg-green-100 text-green-700',
  ua: 'bg-purple-100 text-purple-700',
}

const LEVEL_COLORS: Record<string, string> = {
  'Diploma': 'bg-blue-50 text-blue-600',
  'Sijil': 'bg-green-50 text-green-600',
  'Sarjana Muda': 'bg-purple-50 text-purple-600',
  'Asasi': 'bg-orange-50 text-orange-600',
}

function isRankedCourse(course: EligibleCourse | RankedCourse): course is RankedCourse {
  return 'fit_score' in course
}

interface CourseCardProps {
  course: EligibleCourse | RankedCourse
  rank?: number
  isSaved: boolean
  onToggleSave?: (courseId: string) => void
}

export default function CourseCard({ course, rank, isSaved, onToggleSave }: CourseCardProps) {
  const imageUrl = getFieldImageUrl(course.field)
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
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={course.field}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-gray-400 text-sm">{course.field || 'Course'}</span>
          </div>
        )}

        {/* Rank badge overlay */}
        {rank && (
          <div className="absolute top-2 left-2 w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center shadow">
            <span className="text-white text-sm font-bold">#{rank}</span>
          </div>
        )}

        {/* Save button overlay */}
        {onToggleSave && (
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
      <Link href={`/course/${course.course_id}`} className="flex-1 p-4 flex flex-col">
        {/* Type + Level badges */}
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              TYPE_COLORS[course.source_type] || 'bg-gray-100 text-gray-700'
            }`}
          >
            {TYPE_LABELS[course.source_type] || course.source_type}
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
        <p className="text-gray-500 text-xs mb-2">
          {course.field || 'View course details'}
        </p>

        {/* Merit traffic light */}
        <MeritIndicator label={course.merit_label} color={course.merit_color} />

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

function MeritIndicator({ label, color }: { label: string | null; color: string | null }) {
  if (!label) return null

  const textClass =
    label === 'High' ? 'text-green-700' :
    label === 'Fair' ? 'text-amber-700' :
    'text-red-700'

  const displayLabel =
    label === 'High' ? 'High Chance' :
    label === 'Fair' ? 'Fair Chance' :
    'Low Chance'

  return (
    <div className="flex items-center gap-1.5">
      <span
        className="w-2 h-2 rounded-full inline-block flex-shrink-0"
        style={{ backgroundColor: color || '#95a5a6' }}
      />
      <span className={`text-xs font-medium ${textClass}`}>
        {displayLabel}
      </span>
    </div>
  )
}
