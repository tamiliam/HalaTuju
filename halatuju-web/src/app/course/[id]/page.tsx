'use client'

import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { getCourse, saveCourse, unsaveCourse, type Course, type Institution } from '@/lib/api'
import { useState } from 'react'

export default function CourseDetailPage() {
  const params = useParams()
  const router = useRouter()
  const courseId = params.id as string
  const [isSaved, setIsSaved] = useState(false)
  const [saving, setSaving] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['course', courseId],
    queryFn: () => getCourse(courseId),
    enabled: !!courseId,
  })

  const handleSave = async () => {
    setSaving(true)
    try {
      if (isSaved) {
        await unsaveCourse(courseId)
        setIsSaved(false)
      } else {
        await saveCourse(courseId)
        setIsSaved(true)
      }
    } catch (err) {
      console.error('Failed to save course:', err)
    }
    setSaving(false)
  }

  if (isLoading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
          <p className="text-gray-600">Loading course details...</p>
        </div>
      </main>
    )
  }

  if (error || !data) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Course not found</h1>
          <p className="text-gray-600 mb-6">
            We couldn't find the course you're looking for.
          </p>
          <Link href="/dashboard" className="btn-primary">
            Back to Dashboard
          </Link>
        </div>
      </main>
    )
  }

  const { course, institutions } = data

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.back()}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg
                className="w-5 h-5 text-gray-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
            <Link href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold">H</span>
              </div>
              <span className="font-semibold text-gray-900">HalaTuju</span>
            </Link>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              isSaved
                ? 'bg-primary-100 text-primary-600'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <svg
              className="w-5 h-5"
              fill={isSaved ? 'currentColor' : 'none'}
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
              />
            </svg>
            {saving ? 'Saving...' : isSaved ? 'Saved' : 'Save'}
          </button>
        </div>
      </header>

      {/* Course Header */}
      <section className="bg-white border-b">
        <div className="container mx-auto px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <LevelBadge level={course.level} />
                {course.wbl && (
                  <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
                    Work-Based Learning
                  </span>
                )}
                <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                  {course.department}
                </span>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                {course.course}
              </h1>
              <p className="text-gray-600 mb-4">
                {course.frontend_label || course.field}
              </p>
              {course.semesters && (
                <p className="text-sm text-gray-500">
                  Duration: {course.semesters} semesters
                </p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        <div className="grid md:grid-cols-3 gap-8">
          {/* Left Column - Description */}
          <div className="md:col-span-2 space-y-8">
            {/* About */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                About This Course
              </h2>
              <p className="text-gray-600 leading-relaxed">
                {course.description ||
                  `This ${course.level} programme in ${course.field} prepares students for careers in ${course.department}. The course combines theoretical knowledge with practical skills to ensure graduates are industry-ready.`}
              </p>
            </section>

            {/* Institutions */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Where You Can Study
                {institutions && (
                  <span className="text-gray-500 font-normal ml-2">
                    ({institutions.length} institutions)
                  </span>
                )}
              </h2>
              {institutions && institutions.length > 0 ? (
                <div className="space-y-4">
                  {institutions.map((inst) => (
                    <InstitutionCard key={inst.institution_id} institution={inst} />
                  ))}
                </div>
              ) : (
                <p className="text-gray-500">
                  Institution information not available for this course.
                </p>
              )}
            </section>
          </div>

          {/* Right Column - Quick Info */}
          <div className="space-y-6">
            {/* Quick Facts */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Quick Facts
              </h2>
              <div className="space-y-4">
                <InfoRow label="Level" value={course.level} />
                <InfoRow label="Field" value={course.field} />
                <InfoRow label="Department" value={course.department} />
                {course.semesters && (
                  <InfoRow label="Duration" value={`${course.semesters} semesters`} />
                )}
                <InfoRow label="WBL" value={course.wbl ? 'Yes' : 'No'} />
              </div>
            </section>

            {/* Actions */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Actions
              </h2>
              <div className="space-y-3">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="btn-primary w-full"
                >
                  {isSaved ? 'Remove from Saved' : 'Save This Course'}
                </button>
                <Link
                  href="/dashboard"
                  className="btn-secondary w-full text-center block"
                >
                  Back to Recommendations
                </Link>
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
  )
}

function LevelBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    'Diploma': 'bg-blue-100 text-blue-700',
    'Sijil': 'bg-green-100 text-green-700',
    'Sarjana Muda': 'bg-purple-100 text-purple-700',
    'Asasi': 'bg-orange-100 text-orange-700',
  }

  return (
    <span
      className={`px-3 py-1 rounded-full text-sm font-medium ${
        colors[level] || 'bg-gray-100 text-gray-700'
      }`}
    >
      {level}
    </span>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-gray-500 text-sm">{label}</span>
      <span className="font-medium text-gray-900 text-sm">{value}</span>
    </div>
  )
}

function InstitutionCard({ institution }: { institution: Institution }) {
  const stateColors: Record<string, string> = {
    'Selangor': 'bg-blue-50',
    'Kuala Lumpur': 'bg-red-50',
    'Johor': 'bg-green-50',
    'Penang': 'bg-yellow-50',
    'Sabah': 'bg-purple-50',
    'Sarawak': 'bg-pink-50',
  }

  const hasFees = institution.tuition_fee_semester || institution.registration_fee
  const hasAllowance = institution.monthly_allowance && institution.monthly_allowance > 0

  return (
    <div
      className={`rounded-lg border border-gray-200 p-4 ${
        stateColors[institution.state] || 'bg-gray-50'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900 mb-1">
            {institution.institution_name}
          </h3>
          <p className="text-sm text-gray-500 mb-2">
            {institution.acronym && `(${institution.acronym}) · `}
            {institution.type}
          </p>
          <div className="flex items-center gap-2 text-sm text-gray-600 mb-3">
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            {institution.state}
          </div>

          {/* Fee details */}
          {hasFees && (
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm mb-3">
              {institution.tuition_fee_semester && (
                <>
                  <span className="text-gray-500">Tuition</span>
                  <span className="text-gray-900">{institution.tuition_fee_semester}</span>
                </>
              )}
              {institution.hostel_fee_semester && (
                <>
                  <span className="text-gray-500">Hostel</span>
                  <span className="text-gray-900">{institution.hostel_fee_semester}</span>
                </>
              )}
              {institution.registration_fee && (
                <>
                  <span className="text-gray-500">Registration</span>
                  <span className="text-gray-900">{institution.registration_fee}</span>
                </>
              )}
            </div>
          )}

          {/* Allowance + badges */}
          <div className="flex flex-wrap items-center gap-2">
            {hasAllowance && (
              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded text-xs font-medium">
                RM{institution.monthly_allowance}/month
              </span>
            )}
            {institution.free_hostel && (
              <span className="px-2 py-0.5 bg-sky-100 text-sky-700 rounded text-xs font-medium">
                Free Hostel
              </span>
            )}
            {institution.free_meals && (
              <span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs font-medium">
                Free Meals
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <span
            className={`px-2 py-1 rounded text-xs font-medium ${
              institution.category === 'Public'
                ? 'bg-green-100 text-green-700'
                : 'bg-blue-100 text-blue-700'
            }`}
          >
            {institution.category}
          </span>
          {institution.hyperlink && (
            <a
              href={institution.hyperlink}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 bg-primary-500 text-white rounded-lg text-xs font-medium hover:bg-primary-600 transition-colors"
            >
              Apply
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
