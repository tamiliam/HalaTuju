'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { getCourse, type Course, type Institution, type MascoOccupation, type CourseRequirements } from '@/lib/api'
import { useSavedCourses } from '@/hooks/useSavedCourses'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import RequirementsCard from '@/components/RequirementsCard'
import SpecialConditions from '@/components/SpecialConditions'
import { LoadingSpinner, CourseNotFound, InfoRow, CourseActions } from '@/components/CourseDetailShared'
import { useT } from '@/lib/i18n'
import { useState, useMemo, useCallback } from 'react'
import { STPM_SCHOOLS, type StpmSchool } from '@/data/stpm-schools'
import { MATRIC_COLLEGES, type MatricCollege } from '@/data/matric-colleges'

export default function CourseDetailPage() {
  const params = useParams()
  const courseId = params.id as string
  const { locale, t } = useT()
  const { savedIds, toggleSave } = useSavedCourses()
  const isSaved = savedIds.has(courseId)
  const [isHovering, setIsHovering] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['course', courseId],
    queryFn: () => getCourse(courseId),
    enabled: !!courseId,
  })

  const handleSave = useCallback(() => {
    toggleSave(courseId)
  }, [toggleSave, courseId])

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <CourseNotFound />

  const { course, institutions, career_occupations, requirements, merit_cutoff, merit_type } = data
  const isMatGred = merit_type === 'stpm_mata_gred'
  const isPreU = courseId.startsWith('stpm-') || courseId.startsWith('matric-')
  const isArtsStream = courseId === 'stpm-sains-sosial'

  // Course-level "More Info" link
  const sourceType = requirements?.source_type
  const courseInfoUrl = courseId.startsWith('matric-')
    ? 'https://www.moe.gov.my/pengenalan-matrikulasi'
    : courseId.startsWith('stpm-')
      ? 'https://sst6.moe.gov.my/index.cfm'
      : sourceType === 'pismp'
        ? 'https://pismp.moe.gov.my/iklan_permohonan.cfm'
        : institutions?.[0]?.hyperlink || null

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

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
              {(t(`courses.${course.course_id}.headline`) !== `courses.${course.course_id}.headline` || course.headline || course.headline_en) && (
                <p className="text-lg text-primary-600 font-medium mb-2">
                  {t(`courses.${course.course_id}.headline`) !== `courses.${course.course_id}.headline`
                    ? t(`courses.${course.course_id}.headline`)
                    : locale === 'ms' ? (course.headline || course.headline_en) : (course.headline_en || course.headline)}
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
                {t('courseDetail.aboutTitle')}
              </h2>
              <p className="text-gray-600 leading-relaxed">
                {t(`courses.${course.course_id}.description`) !== `courses.${course.course_id}.description`
                  ? t(`courses.${course.course_id}.description`)
                  : locale === 'ms'
                    ? (course.description || course.description_en || t('courses.descriptionFallback', { level: course.level, field: course.field, department: course.department }))
                    : (course.description_en || course.description || t('courses.descriptionFallback', { level: course.level, field: course.field, department: course.department }))}
              </p>
              {courseInfoUrl && (
                <div className="flex justify-end mt-4">
                  <a
                    href={courseInfoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 bg-primary-500 text-white rounded-lg text-xs font-medium hover:bg-primary-600 transition-colors whitespace-nowrap"
                  >
                    More Info
                  </a>
                </div>
              )}
            </section>

            {/* Career Pathways */}
            {career_occupations && career_occupations.length > 0 && (
              <section className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-2">
                  {t('courseDetail.careerPathways')}
                </h2>
                <p className="text-sm text-gray-500 mb-4">
                  {t('courseDetail.careerPathwaysDesc')}
                </p>
                <div className="flex flex-wrap gap-2">
                  {career_occupations.map((occ) => (
                    <a
                      key={occ.masco_code}
                      href={occ.emasco_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium hover:bg-indigo-100 transition-colors"
                    >
                      {occ.job_title}
                      <svg className="w-3.5 h-3.5 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  ))}
                </div>
              </section>
            )}

            {/* Institutions */}
            {courseId.startsWith('stpm-') ? (
              <StpmInstitutionsSection courseId={courseId} />
            ) : courseId.startsWith('matric-') ? (
              <MatricInstitutionsSection courseId={courseId} />
            ) : (
              <section className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                  {t('courseDetail.whereToStudy')}
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
                    {t('courseDetail.noInstitutions')}
                  </p>
                )}
              </section>
            )}
          </div>

          {/* Right Column - Quick Info */}
          <div className="space-y-6">
            {/* Quick Facts */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {t('courseDetail.quickFacts')}
              </h2>
              <div className="space-y-4">
                <InfoRow label="Level" value={course.level} />
                <InfoRow label="Field" value={course.field} />
                {!isPreU && <InfoRow label="Department" value={course.department} />}
                {course.semesters && (
                  <InfoRow label="Duration" value={`${course.semesters} semesters`} />
                )}
                {!isPreU && <InfoRow label="WBL" value={course.wbl ? 'Yes' : 'No'} />}
                {merit_cutoff != null && (
                  <div className="pt-2 mt-2 border-t border-gray-100">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-500 text-sm">
                        {isMatGred ? t('courseDetail.maxGradePoints') : 'Avg. Merit'}
                      </span>
                      <span className={`font-medium text-sm ${
                        isMatGred
                          ? (isArtsStream
                              ? (merit_cutoff <= 12 ? 'text-green-600' : merit_cutoff <= 18 ? 'text-amber-600' : 'text-red-600')
                              : (merit_cutoff <= 18 ? 'text-green-600' : 'text-amber-600'))
                          : (merit_cutoff >= 80 ? 'text-green-600' : merit_cutoff >= 60 ? 'text-amber-600' : 'text-red-600')
                      }`}>
                        {merit_cutoff.toFixed(1)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Requirements */}
            {requirements && <RequirementsCard requirements={requirements} />}

            {/* Special Conditions */}
            {requirements && (
              <SpecialConditions
                reqInterview={requirements.special?.some((s: { key: string }) => s.key === 'req_interview')}
                noColorblind={requirements.special?.some((s: { key: string }) => s.key === 'no_colorblind')}
                reqMedicalFitness={requirements.special?.some((s: { key: string }) => s.key === 'req_medical_fitness')}
              />
            )}

            {/* Subject Key for STPM courses */}
            {courseId.startsWith('stpm-') && (
              <SubjectLegend stream={courseId === 'stpm-sains' ? 'Sains' : 'Sains Sosial'} />
            )}

            {/* Actions */}
            <CourseActions
              isSaved={isSaved}
              isHovering={isHovering}
              onSave={handleSave}
              onHoverStart={() => setIsHovering(true)}
              onHoverEnd={() => setIsHovering(false)}
            />
          </div>
        </div>
      </div>

      <AppFooter />
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
          {institution.url && (
            <a
              href={institution.url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 bg-primary-500 text-white rounded-lg text-xs font-medium hover:bg-primary-600 transition-colors"
            >
              More Info
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

// ── STPM rich institution section ────────────────────────────────────────

const COMMON_SUBJECTS = new Set(['BI (MUET)', 'PA', 'BM'])
const SCIENCE_SUBJECTS = new Set(['BIO', 'CHE', 'PHY', 'MT', 'MM'])
const SOCIAL_SUBJECTS = new Set(['EKO', 'SEJ', 'GEO', 'PP', 'PAKN', 'SS', 'SV', 'BT', 'BC', 'KMK', 'ICT', 'L.ENG'])

const SUBJECT_COLORS: Record<string, string> = {
  BIO: 'bg-green-100 text-green-700',
  CHE: 'bg-amber-100 text-amber-700',
  PHY: 'bg-blue-100 text-blue-700',
  MT: 'bg-indigo-100 text-indigo-700',
  MM: 'bg-indigo-100 text-indigo-700',
  EKO: 'bg-emerald-100 text-emerald-700',
  SEJ: 'bg-rose-100 text-rose-700',
  GEO: 'bg-teal-100 text-teal-700',
  PP: 'bg-orange-100 text-orange-700',
  PAKN: 'bg-purple-100 text-purple-700',
  SS: 'bg-pink-100 text-pink-700',
  SV: 'bg-cyan-100 text-cyan-700',
  BT: 'bg-red-100 text-red-700',
  BC: 'bg-yellow-100 text-yellow-700',
  KMK: 'bg-fuchsia-100 text-fuchsia-700',
  ICT: 'bg-sky-100 text-sky-700',
  'L.ENG': 'bg-lime-100 text-lime-700',
}

const SUBJECT_NAMES: Record<string, string> = {
  BIO: 'Biology',
  CHE: 'Chemistry',
  PHY: 'Physics',
  MT: 'Mathematics (T)',
  MM: 'Mathematics (M)',
  EKO: 'Economics',
  SEJ: 'History',
  GEO: 'Geography',
  PP: 'Business Studies',
  PAKN: 'Accounting',
  SS: 'Literature',
  SV: 'Visual Arts',
  BT: 'Bahasa Tamil',
  BC: 'Bahasa Cina',
  KMK: 'Kesusasteraan Melayu Komunikatif',
  ICT: 'Information & Communication Technology',
  'L.ENG': 'Literature in English',
}

function SubjectLegend({ stream }: { stream: string }) {
  const subjects = stream === 'Sains'
    ? ['BIO', 'CHE', 'PHY', 'MT', 'MM']
    : ['EKO', 'PP', 'PAKN', 'SEJ', 'GEO', 'SS', 'SV', 'BT', 'BC', 'KMK', 'ICT', 'L.ENG']

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">Subject Key</h2>
      <div className="space-y-2">
        {subjects.map(code => (
          <div key={code} className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${SUBJECT_COLORS[code]}`}>
              {code}
            </span>
            <span className="text-xs text-gray-600">{SUBJECT_NAMES[code]}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function filterSubjects(raw: string, stream: string): string[] {
  const relevant = stream === 'Sains' ? SCIENCE_SUBJECTS : SOCIAL_SUBJECTS
  return raw
    .split('; ')
    .filter(s => !COMMON_SUBJECTS.has(s) && relevant.has(s))
}

function formatPhone(raw: string): string {
  const d = raw.replace(/\D/g, '')
  if (d.length === 10) return `${d.slice(0, 3)}-${d.slice(3, 6)} ${d.slice(6)}`
  if (d.length === 9) return `${d.slice(0, 2)}-${d.slice(2, 5)} ${d.slice(5)}`
  if (d.length === 11) return `${d.slice(0, 3)}-${d.slice(3, 7)} ${d.slice(7)}`
  return raw
}

const STPM_STREAM_MAP: Record<string, string> = {
  'stpm-sains': 'Sains',
  'stpm-sains_sosial': 'Sains Sosial',
}

const PAGE_SIZE = 50

function StpmInstitutionsSection({ courseId }: { courseId: string }) {
  const { t } = useT()
  const streamName = STPM_STREAM_MAP[courseId] || 'Sains'
  const [stateFilter, setStateFilter] = useState('')
  const [ppdFilter, setPpdFilter] = useState('')
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)

  const streamSchools = useMemo(() => {
    return STPM_SCHOOLS.filter(s => s.streams.includes(streamName))
  }, [streamName])

  const allStates = useMemo(() => {
    return Array.from(new Set(streamSchools.map(s => s.state))).sort()
  }, [streamSchools])

  const availablePpds = useMemo(() => {
    let schools = streamSchools
    if (stateFilter) schools = schools.filter(s => s.state === stateFilter)
    return Array.from(new Set(schools.map(s => s.ppd))).sort()
  }, [streamSchools, stateFilter])

  const filteredSchools = useMemo(() => {
    let schools = streamSchools
    if (stateFilter) schools = schools.filter(s => s.state === stateFilter)
    if (ppdFilter) schools = schools.filter(s => s.ppd === ppdFilter)
    return schools
  }, [streamSchools, stateFilter, ppdFilter])

  const displayedSchools = filteredSchools.slice(0, displayCount)
  const remaining = filteredSchools.length - displayCount

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-4 sm:p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        {t('courseDetail.whereToStudy')}
        <span className="text-gray-500 font-normal ml-2">
          ({filteredSchools.length})
        </span>
      </h2>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={stateFilter}
          onChange={e => { setStateFilter(e.target.value); setPpdFilter(''); setDisplayCount(PAGE_SIZE) }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          <option value="">All States</option>
          {allStates.map(state => (
            <option key={state} value={state}>{state}</option>
          ))}
        </select>
        <select
          value={ppdFilter}
          onChange={e => { setPpdFilter(e.target.value); setDisplayCount(PAGE_SIZE) }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          <option value="">All Districts</option>
          {availablePpds.map(ppd => (
            <option key={ppd} value={ppd}>{ppd}</option>
          ))}
        </select>
      </div>

      <div className="max-h-[600px] overflow-y-auto space-y-3">
        {displayedSchools.length > 0 ? (
          displayedSchools.map(school => (
            <StpmSchoolCard key={school.code} school={school} stream={streamName} />
          ))
        ) : (
          <p className="text-gray-400 text-center py-8">
            No schools match the selected filters.
          </p>
        )}
      </div>

      {remaining > 0 && (
        <div className="text-center pt-4">
          <button
            className="btn-secondary"
            onClick={() => setDisplayCount(displayCount + PAGE_SIZE)}
          >
            Load More ({remaining} remaining)
          </button>
        </div>
      )}
    </section>
  )
}

function StpmSchoolCard({ school, stream }: { school: StpmSchool; stream: string }) {
  const subjects = school.subjects ? filterSubjects(school.subjects, stream) : []

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 text-sm sm:text-base mb-1 truncate">
            {school.name}
          </h3>
          <p className="text-xs sm:text-sm text-gray-500 mb-2">
            {school.state} &middot; {school.ppd}
          </p>
          {subjects.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {subjects.map(s => (
                <span key={s} className={`px-1.5 py-0.5 rounded text-[10px] sm:text-xs font-medium ${SUBJECT_COLORS[s] || 'bg-gray-100 text-gray-600'}`}>
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
        {school.phone && (
          <a
            href={`tel:${school.phone}`}
            className="text-xs sm:text-sm text-primary-600 hover:text-primary-800 whitespace-nowrap flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            {formatPhone(school.phone)}
          </a>
        )}
      </div>
    </div>
  )
}

// ── Matric rich institution section ──────────────────────────────────────

const MATRIC_TRACK_MAP: Record<string, string> = {
  'matric-sains': 'sains',
  'matric-sains_komputer': 'sains_komputer',
  'matric-kejuruteraan': 'kejuruteraan',
  'matric-perakaunan': 'perakaunan',
}

const TRACK_COLOURS: Record<string, string> = {
  sains: 'bg-green-100 text-green-800',
  sains_komputer: 'bg-blue-100 text-blue-800',
  kejuruteraan: 'bg-orange-100 text-orange-800',
  perakaunan: 'bg-purple-100 text-purple-800',
}

const TRACK_LABELS: Record<string, string> = {
  sains: 'Sains',
  sains_komputer: 'Sains Komputer',
  kejuruteraan: 'Kejuruteraan',
  perakaunan: 'Perakaunan',
}

function MatricInstitutionsSection({ courseId }: { courseId: string }) {
  const { t } = useT()
  const trackId = MATRIC_TRACK_MAP[courseId] || 'sains'
  const [stateFilter, setStateFilter] = useState('')

  const trackColleges = useMemo(() => {
    let colleges = MATRIC_COLLEGES.filter(c =>
      c.tracks.includes(trackId as MatricCollege['tracks'][number])
    )
    if (stateFilter) colleges = colleges.filter(c => c.state === stateFilter)
    return colleges
  }, [trackId, stateFilter])

  const availableStates = useMemo(() => {
    const filtered = MATRIC_COLLEGES.filter(c =>
      c.tracks.includes(trackId as MatricCollege['tracks'][number])
    )
    return Array.from(new Set(filtered.map(c => c.state))).sort()
  }, [trackId])

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-4 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h2 className="text-xl font-semibold text-gray-900">
          {t('courseDetail.whereToStudy')}
          <span className="text-gray-400 font-normal ml-2 text-base">
            ({trackColleges.length})
          </span>
        </h2>
        <select
          value={stateFilter}
          onChange={e => setStateFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          <option value="">All States</option>
          {availableStates.map(state => (
            <option key={state} value={state}>{state}</option>
          ))}
        </select>
      </div>

      {trackColleges.length > 0 ? (
        <div className="space-y-3">
          {trackColleges.map(college => (
            <MatricCollegeCard key={college.id} college={college} trackId={trackId} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500 text-center py-8">
          No colleges found for the selected filters.
        </p>
      )}
    </section>
  )
}

function MatricCollegeCard({ college, trackId }: { college: MatricCollege; trackId: string }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h3 className="font-semibold text-gray-900 mb-2">{college.name}</h3>

      <div className="flex items-center gap-1.5 text-sm text-gray-500 mb-3">
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        {college.state}
      </div>

      <div className="flex flex-wrap gap-1.5 mb-3">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TRACK_COLOURS[trackId] || 'bg-gray-100 text-gray-700'}`}>
          {TRACK_LABELS[trackId] || trackId}
        </span>
      </div>

      <div className="flex items-center gap-2 text-sm text-gray-600 mb-1.5">
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
        </svg>
        {college.phone}
      </div>

      <a
        href={`https://${college.website}`}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 hover:underline"
      >
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
        {college.website}
      </a>
    </div>
  )
}
