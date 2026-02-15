'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { checkEligibility, getSavedCourses, saveCourse, unsaveCourse, type StudentProfile, type EligibleCourse } from '@/lib/api'
import { getSession } from '@/lib/supabase'

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

export default function DashboardPage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')
  const [displayCount, setDisplayCount] = useState(20)
  const [token, setToken] = useState<string | null>(null)
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())

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

  if (isLoading) {
    return <LoadingScreen />
  }

  if (!profile) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            No profile found
          </h1>
          <p className="text-gray-600 mb-6">
            Please complete the onboarding to see your recommendations.
          </p>
          <Link href="/onboarding/stream" className="btn-primary">
            Start Onboarding
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
            <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold">H</span>
            </div>
            <span className="font-semibold text-gray-900">HalaTuju</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/saved" className="text-gray-600 hover:text-gray-900">
              Saved
            </Link>
            <Link href="/settings" className="text-gray-600 hover:text-gray-900">
              Settings
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
                Your Course Recommendations
              </h1>
              <p className="text-gray-600">
                Based on your SPM grades and profile, here are courses you qualify for.
              </p>
            </div>
            <Link
              href="/onboarding/grades"
              className="btn-secondary whitespace-nowrap"
            >
              Edit Profile
            </Link>
          </div>

          {/* Stats */}
          {eligibilityData && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t">
              <StatCard
                number={eligibilityData.eligible_courses.length}
                label="Total Eligible"
              />
              <StatCard
                number={eligibilityData.stats.poly || 0}
                label="Polytechnic"
              />
              <StatCard
                number={eligibilityData.stats.tvet || 0}
                label="TVET"
              />
              <StatCard
                number={eligibilityData.stats.ua || 0}
                label="University"
              />
            </div>
          )}
        </div>

        {/* Loading State */}
        {eligibilityLoading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
            <p className="text-gray-600">Checking your eligibility...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <p className="text-red-600 mb-4">
              Failed to load recommendations. Please try again.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="btn-primary"
            >
              Retry
            </button>
          </div>
        )}

        {/* Course List */}
        {eligibilityData && (() => {
          const filteredCourses = filter === 'all'
            ? eligibilityData.eligible_courses
            : eligibilityData.eligible_courses.filter(c => c.source_type === filter)
          const displayedCourses = filteredCourses.slice(0, displayCount)
          const remaining = filteredCourses.length - displayCount

          return (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">
                  Eligible Courses ({filteredCourses.length})
                </h2>
                <select
                  className="input w-auto"
                  value={filter}
                  onChange={(e) => {
                    setFilter(e.target.value)
                    setDisplayCount(20)
                  }}
                >
                  <option value="all">All Types</option>
                  <option value="poly">Polytechnic</option>
                  <option value="tvet">TVET</option>
                  <option value="ua">University</option>
                </select>
              </div>

              <div className="grid gap-4">
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
                    Load More ({remaining} remaining)
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

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-white">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mb-4" />
        <p className="text-gray-600">Loading your profile...</p>
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

function CourseCard({
  course,
  isSaved,
  onToggleSave,
}: {
  course: EligibleCourse
  isSaved: boolean
  onToggleSave?: (courseId: string) => void
}) {
  const typeLabels: Record<string, string> = {
    poly: 'Polytechnic',
    tvet: 'TVET',
    ua: 'University',
  }

  const typeColors: Record<string, string> = {
    poly: 'bg-blue-100 text-blue-700',
    tvet: 'bg-green-100 text-green-700',
    ua: 'bg-purple-100 text-purple-700',
  }

  const levelColors: Record<string, string> = {
    'Diploma': 'bg-blue-50 text-blue-600',
    'Sijil': 'bg-green-50 text-green-600',
    'Sarjana Muda': 'bg-purple-50 text-purple-600',
    'Asasi': 'bg-orange-50 text-orange-600',
  }

  const imageUrl = getFieldImageUrl(course.field)

  return (
    <div className="bg-white rounded-xl border border-gray-200 hover:border-primary-300 hover:shadow-sm transition-all overflow-hidden">
      <div className="flex">
        {/* Field image thumbnail */}
        {imageUrl && (
          <div className="hidden sm:block w-28 md:w-36 flex-shrink-0 relative">
            <img
              src={imageUrl}
              alt={course.field}
              className="absolute inset-0 w-full h-full object-cover"
            />
          </div>
        )}

        {/* Course details — clickable link */}
        <Link href={`/course/${course.course_id}`} className="flex-1 p-5">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span
              className={`px-2 py-1 rounded text-xs font-medium ${
                typeColors[course.source_type] || 'bg-gray-100 text-gray-700'
              }`}
            >
              {typeLabels[course.source_type] || course.source_type}
            </span>
            {course.level && (
              <span
                className={`px-2 py-1 rounded text-xs font-medium ${
                  levelColors[course.level] || 'bg-gray-50 text-gray-600'
                }`}
              >
                {course.level}
              </span>
            )}
            {course.merit_cutoff && (
              <span className="text-xs text-gray-500">
                Merit: {course.merit_cutoff}
              </span>
            )}
          </div>
          <h3 className="text-base font-semibold text-gray-900 mb-1">
            {course.course_name || course.course_id}
          </h3>
          <p className="text-gray-500 text-sm">
            {course.field || 'View course details'}
          </p>
        </Link>

        {/* Save button + Arrow */}
        <div className="flex items-center gap-2 pr-4">
          {onToggleSave && (
            <button
              onClick={(e) => {
                e.preventDefault()
                onToggleSave(course.course_id)
              }}
              className="p-2 rounded-full hover:bg-gray-100 transition-colors"
              aria-label={isSaved ? 'Remove from saved' : 'Save course'}
            >
              <svg
                className={`w-5 h-5 ${isSaved ? 'text-primary-500 fill-primary-500' : 'text-gray-400'}`}
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
          <Link href={`/course/${course.course_id}`} className="text-gray-400">
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </Link>
        </div>
      </div>
    </div>
  )
}
