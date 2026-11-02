'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { getCourse, type Course, type Institution, type CourseRequirements } from '@/lib/api'
import { useSavedCourses } from '@/hooks/useSavedCourses'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import CourseHeader from '@/components/CourseHeader'
import RequirementsCard from '@/components/RequirementsCard'
import SpecialConditions from '@/components/SpecialConditions'
import { LoadingSpinner, CourseNotFound, InfoRow, CourseActions, CourseSaveBar } from '@/components/CourseDetailShared'
import CareerPathways from '@/components/CareerPathways'
import { useT } from '@/lib/i18n'
import { useFieldTaxonomy } from '@/hooks/useFieldTaxonomy'
import { useState, useCallback } from 'react'
import { StpmInstitutionsSection, MatricInstitutionsSection, SubjectLegend } from '@/components/course/PreUInstitutions'
// Mobile M3: "show all" on a phone (the `discovery` slice), loaded by this PAGE.
import '@/lib/messagesDiscovery'
import { PHONE_GUTTER, PHONE_ROWS, PHONE_SECTION } from '@/lib/phoneSection'

export default function CourseDetailPage() {
  const params = useParams()
  const courseId = params.id as string
  const { locale, t } = useT()
  const { getFieldName } = useFieldTaxonomy(locale)
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

  // Course-level headline / subtitle
  const sourceType = requirements?.source_type
  const headlineKey = `courses.${course.course_id}.headline`
  const headlineI18n = t(headlineKey)
  const subtitle = headlineI18n !== headlineKey
    ? headlineI18n
    : locale === 'ms'
      ? (course.headline || course.headline_en)
      : (course.headline_en || course.headline)

  // Course-level "More Info" link
  const courseInfoUrl = courseId.startsWith('matric-')
    ? 'https://www.moe.gov.my/pengenalan-matrikulasi'
    : courseId.startsWith('stpm-')
      ? 'https://sst6.moe.gov.my/index.cfm'
      : sourceType === 'pismp'
        ? 'https://pismp.moe.gov.my/iklan_permohonan.cfm'
        : institutions?.[0]?.hyperlink || null

  return (
    <main className="min-h-screen bg-ground-50">
      <AppHeader />

      <CourseHeader
        sourceType={sourceType || 'university'}
        pathwayType={requirements?.pathway_type}
        level={course.level}
        title={course.course}
        subtitle={subtitle || undefined}
      />

      {/* Main Content.
          ⚠ ON A PHONE THE TWO COLUMNS DISSOLVE (Mobile M3): each column is `contents` below `md`, so
          every section is an item of ONE flex column and takes its phone place from `order-*` —
          quick facts and entry requirements first, the long institution list last. From `md` the
          columns are real again and the order classes are reset. Reading order (screen readers,
          Tab) stays the source order, the desktop's; each section keeps its own heading
          (docs/decisions.md, Mobile M3). Every item is `min-w-0`: a `truncate` school name used to
          set the column's width and push the page 8 px past a 375 px screen. */}
      <div className={`container mx-auto ${PHONE_GUTTER} pb-6 md:py-8`}>
        <div className="flex flex-col md:grid md:grid-cols-3 md:gap-8">
          {/* Left Column - Description */}
          <div className="contents md:col-span-2 md:block md:min-w-0 md:space-y-8">
            {/* About */}
            <div className="order-4 min-w-0 md:order-none">
            <section className={PHONE_SECTION}>
              <h2 className="text-xl font-semibold text-ground-900 mb-4">
                {t('courseDetail.aboutTitle')}
              </h2>
              <p className="text-ground-600 leading-relaxed">
                {t(`courses.${course.course_id}.description`) !== `courses.${course.course_id}.description`
                  ? t(`courses.${course.course_id}.description`)
                  : locale === 'ms'
                    ? (course.description || course.description_en || t('courses.descriptionFallback', { level: course.level, field: getFieldName(course.field_key), department: course.department }))
                    : (course.description_en || course.description || t('courses.descriptionFallback', { level: course.level, field: getFieldName(course.field_key), department: course.department }))}
              </p>
              {courseInfoUrl && (
                <div className="flex justify-end mt-4">
                  <a
                    href={courseInfoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-11 items-center px-4 py-1.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover transition-colors whitespace-nowrap"
                  >
                    More Info
                  </a>
                </div>
              )}
            </section>
            </div>

            {/* Career Pathways */}
            <div className="order-5 min-w-0 empty:hidden md:order-none">
            <CareerPathways occupations={career_occupations || []} />
            </div>

            {/* Institutions */}
            <div className="order-6 min-w-0 md:order-none">
            {courseId.startsWith('stpm-') ? (
              <StpmInstitutionsSection courseId={courseId} />
            ) : courseId.startsWith('matric-') ? (
              <MatricInstitutionsSection courseId={courseId} />
            ) : (
              <section className={PHONE_SECTION}>
                <h2 className="text-xl font-semibold text-ground-900 mb-4">
                  {t('courseDetail.whereToStudy')}
                  {institutions && (
                    <span className="text-ground-500 font-normal ml-2">
                      ({t(institutions.length === 1 ? 'courseDetail.institutionCount' : 'courseDetail.institutionsCount', { count: String(institutions.length) })})
                    </span>
                  )}
                </h2>
                {institutions && institutions.length > 0 ? (
                  <InstitutionList institutions={institutions} />
                ) : (
                  <p className="text-ground-500">
                    {t('courseDetail.noInstitutions')}
                  </p>
                )}
              </section>
            )}
            </div>
          </div>

          {/* Right Column - Quick Info */}
          <div className="contents md:block md:min-w-0 md:space-y-6">
            {/* Quick Facts */}
            <div className="order-1 min-w-0 md:order-none">
            <section className={PHONE_SECTION}>
              <h2 className="text-lg font-semibold text-ground-900 mb-4">
                {t('courseDetail.quickFacts')}
              </h2>
              <div className="space-y-4">
                <InfoRow label="Level" value={course.level} />
                <InfoRow label="Field" value={getFieldName(course.field_key)} />
                {!isPreU && <InfoRow label="Department" value={course.department} />}
                {course.semesters && (
                  <InfoRow label="Duration" value={`${course.semesters} semesters`} />
                )}
                {!isPreU && <InfoRow label="WBL" value={course.wbl ? 'Yes' : 'No'} />}
                {merit_cutoff != null && (
                  <div className="pt-2 mt-2 border-t border-ground-100">
                    <div className="flex justify-between items-center">
                      <span className="text-ground-500 text-sm">
                        {isMatGred ? t('courseDetail.maxGradePoints') : 'Avg. Merit'}
                      </span>
                      <span className={`font-medium text-sm ${
                        isMatGred
                          ? (isArtsStream
                              ? (merit_cutoff <= 12 ? 'text-positive-700' : merit_cutoff <= 18 ? 'text-caution-700' : 'text-critical-600')
                              : (merit_cutoff <= 18 ? 'text-positive-700' : 'text-caution-700'))
                          : (merit_cutoff >= 80 ? 'text-positive-700' : merit_cutoff >= 60 ? 'text-caution-700' : 'text-critical-600')
                      }`}>
                        {merit_cutoff.toFixed(1)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </section>
            </div>

            {/* Requirements */}
            <div className="order-2 min-w-0 empty:hidden md:order-none">
            {requirements && <RequirementsCard requirements={requirements} />}
            </div>

            {/* Special Conditions */}
            <div className="order-3 min-w-0 empty:hidden md:order-none">
            {requirements && (
              <SpecialConditions
                reqInterview={requirements.special?.some((s: { key: string }) => s.key === 'req_interview')}
                noColorblind={requirements.special?.some((s: { key: string }) => s.key === 'no_colorblind')}
                reqMedicalFitness={requirements.special?.some((s: { key: string }) => s.key === 'req_medical_fitness')}
                reqMale={requirements.general?.some((s: { key: string }) => s.key === 'req_male')}
                reqFemale={requirements.general?.some((s: { key: string }) => s.key === 'req_female')}
                single={requirements.general?.some((s: { key: string }) => s.key === 'single')}
                noDisability={requirements.general?.some((s: { key: string }) => s.key === 'no_disability')}
              />
            )}
            </div>

            {/* Subject Key for STPM courses */}
            {courseId.startsWith('stpm-') && (
              <div className="order-7 min-w-0 md:order-none">
              <SubjectLegend stream={courseId === 'stpm-sains' ? 'Sains' : 'Sains Sosial'} />
              </div>
            )}

            {/* Actions — on a phone only "back"; Save is the sticky bar below */}
            <div className="order-8 min-w-0 md:order-none">
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
      </div>

      <CourseSaveBar isSaved={isSaved} onSave={handleSave} />

      <AppFooter />
    </main>
  )
}

/** How many institutions a phone shows before "Show all N institutions" (Mobile M3). */
const PHONE_INSTITUTIONS = 3

/**
 * The institutions, all of them from `md`; on a phone the first three and a button for the rest —
 * eighteen polytechnic cards used to stand between the student and everything below them.
 */
function InstitutionList({ institutions }: { institutions: Institution[] }) {
  const { t } = useT()
  const [all, setAll] = useState(false)
  const hidden = institutions.length - PHONE_INSTITUTIONS
  return (
    <div className={PHONE_ROWS}>
      {institutions.map((inst, i) => (
        <div key={inst.institution_id} className={!all && i >= PHONE_INSTITUTIONS ? 'hidden md:block' : undefined}>
          <InstitutionCard institution={inst} />
        </div>
      ))}
      {!all && hidden > 0 && (
        <button type="button" onClick={() => setAll(true)}
          className="flex min-h-11 w-full items-center justify-center rounded-lg border border-ground-300 px-4 text-sm font-medium text-primary-600 hover:bg-ground-50 md:hidden">
          {t('discovery.showAllInstitutions', { count: String(institutions.length) })}
        </button>
      )}
    </div>
  )
}

function InstitutionCard({ institution }: { institution: Institution }) {
  // ⚠ THE STATE TINT IS GONE (Layer 1 F6). It gave a pastel card background to six of Malaysia's
  // sixteen states and `bg-gray-50` to the other ten, so the colour asserted a distinction that
  // stopped a third of the way through the set — and the codemod had just renamed four of the six
  // onto TONES, which additionally claimed Kuala Lumpur was an error and Johor a success. Every
  // institution card now takes what ten of the sixteen already had. The state is written on the
  // card in words, which is where that fact belongs.
  const hasFees = institution.tuition_fee_semester || institution.registration_fee
  const hasAllowance = institution.monthly_allowance && institution.monthly_allowance > 0

  return (
    <div
      className="py-3 md:rounded-lg md:border md:border-ground-200 md:bg-ground-50 md:p-4"
    >
      {/* A phone stacks the badge and link UNDER the name (Mobile M3): side by side they squeezed it. */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-ground-900 mb-1 break-words">
            {institution.institution_name}
          </h3>
          <p className="text-sm text-ground-500 mb-2">
            {institution.acronym && `(${institution.acronym}) · `}
            {institution.type}
          </p>
          <div className="flex items-center gap-2 text-sm text-ground-600 mb-3">
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
                  <span className="text-ground-500">Tuition</span>
                  <span className="text-ground-900">{institution.tuition_fee_semester}</span>
                </>
              )}
              {institution.hostel_fee_semester && (
                <>
                  <span className="text-ground-500">Hostel</span>
                  <span className="text-ground-900">{institution.hostel_fee_semester}</span>
                </>
              )}
              {institution.registration_fee && (
                <>
                  <span className="text-ground-500">Registration</span>
                  <span className="text-ground-900">{institution.registration_fee}</span>
                </>
              )}
            </div>
          )}

          {/* Allowance + badges */}
          <div className="flex flex-wrap items-center gap-2">
            {hasAllowance && (
              <span className="px-2 py-0.5 bg-positive-100 text-positive-700 rounded text-xs font-medium">
                RM{institution.monthly_allowance}/month
              </span>
            )}
            {institution.free_hostel && (
              <span className="px-2 py-0.5 bg-info-100 text-info-700 rounded text-xs font-medium">
                Free Hostel
              </span>
            )}
            {institution.free_meals && (
              <span className="px-2 py-0.5 bg-info-100 text-info-700 rounded text-xs font-medium">
                Free Meals
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 sm:flex-col sm:items-end">
          <span
            className={`px-2 py-1 rounded text-xs font-medium ${
              institution.category === 'Public'
                ? 'bg-positive-100 text-positive-700'
                : 'bg-info-100 text-info-700'
            }`}
          >
            {institution.category}
          </span>
          {institution.url && (
            <a
              href={institution.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center px-4 py-1.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover transition-colors"
            >
              More Info
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
