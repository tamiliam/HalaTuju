'use client'

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { getStpmCourseDetail } from '@/lib/api'
import { useSavedCourses } from '@/hooks/useSavedCourses'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import CourseHeader from '@/components/CourseHeader'
import SpecialConditions from '@/components/SpecialConditions'
import { LoadingSpinner, CourseNotFound, InfoRow, CourseActions } from '@/components/CourseDetailShared'
import { useT } from '@/lib/i18n'
import { useState, useCallback } from 'react'

export default function StpmCourseDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { t } = useT()
  const { savedIds, toggleSave } = useSavedCourses()
  const isSaved = savedIds.has(id)
  const [isHovering, setIsHovering] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['stpm_course', id],
    queryFn: () => getStpmCourseDetail(id),
  })

  const handleSave = useCallback(() => {
    toggleSave(id)
  }, [toggleSave, id])

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <CourseNotFound />

  const streamLabel = data.stream === 'science' ? 'Science' : data.stream === 'arts' ? 'Arts' : 'Science / Arts'

  const { req_interview, no_colorblind, req_medical_fitness } = data.requirements

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <CourseHeader
        sourceType="university"
        level="Ijazah Sarjana Muda"
        title={data.course_name}
        subtitle={data.headline || data.university}
      />

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        <div className="grid md:grid-cols-3 gap-8">
          {/* Left Column */}
          <div className="md:col-span-2 space-y-8">
            {/* About */}
            {data.description && (
              <section className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                  {t('courseDetail.aboutTitle')}
                </h2>
                <p className="text-gray-600 leading-relaxed">
                  {data.description}
                </p>
                {data.mohe_url && (
                  <div className="flex justify-end mt-4">
                    <a
                      href={data.mohe_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 bg-primary-500 text-white rounded-lg text-xs font-medium hover:bg-primary-600 transition-colors whitespace-nowrap"
                    >
                      More Info
                    </a>
                  </div>
                )}
              </section>
            )}

            {/* Institution */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                {t('courseDetail.whereToStudy')}
                <span className="text-gray-500 font-normal ml-2">(1 institution)</span>
              </h2>
              {data.institution ? (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900 mb-1">
                        {data.institution.institution_name}
                      </h3>
                      <p className="text-sm text-gray-500 mb-2">
                        {data.institution.acronym && `(${data.institution.acronym}) · `}
                        {data.institution.type}
                      </p>
                      {data.institution.state && (
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          {data.institution.state}
                        </div>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700">
                        {data.institution.category}
                      </span>
                      {data.institution.url && (
                        <a
                          href={data.institution.url}
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
              ) : (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <h3 className="font-semibold text-gray-900 mb-1">{data.university}</h3>
                  <p className="text-sm text-gray-500">Universiti Awam</p>
                </div>
              )}
            </section>
          </div>

          {/* Right Column - Sidebar */}
          <div className="space-y-6">
            {/* Quick Facts */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {t('courseDetail.quickFacts')}
              </h2>
              <div className="space-y-4">
                <InfoRow label="Level" value="Ijazah Sarjana Muda" />
                {data.field && <InfoRow label="Field" value={data.field} />}
                {data.category && <InfoRow label="Category" value={data.category} />}
                <InfoRow label="Stream" value={streamLabel} />
                {data.merit_score != null && (
                  <div className="pt-2 mt-2 border-t border-gray-100">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-500 text-sm">Avg. Merit</span>
                      <span className={`font-medium text-sm ${
                        data.merit_score >= 80 ? 'text-green-600' : data.merit_score >= 60 ? 'text-amber-600' : 'text-red-600'
                      }`}>
                        {data.merit_score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Entry Requirements — unified card */}
            <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {/* Header */}
              <div className="px-5 pt-5 pb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                  <svg className="w-[18px] h-[18px] text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {t('courseDetail.requirements')}
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-100 text-purple-700">
                  Universiti
                </span>
              </div>

              <div className="px-5 pb-5 space-y-4">
                {/* General Requirements */}
                {(data.requirements.req_malaysian || data.requirements.req_bumiputera) && (
                  <div>
                    <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                      {t('courseDetail.generalReq')}
                    </h3>
                    <div className="space-y-2">
                      {data.requirements.req_malaysian && (
                        <div className="flex items-start gap-2.5">
                          <CheckIcon color="gray" />
                          <span className="text-[13px] text-gray-700 leading-snug">{t('stpm.malaysianOnly')}</span>
                        </div>
                      )}
                      {data.requirements.req_bumiputera && (
                        <div className="flex items-start gap-2.5">
                          <CheckIcon color="gray" />
                          <span className="text-[13px] text-gray-700 leading-snug">{t('stpm.bumiputeraOnly')}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* STPM Requirements — key-value table */}
                <div>
                  <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    {t('stpm.requirements')}
                  </h3>
                  <div className="rounded-lg border border-gray-100 divide-y divide-gray-100">
                    <div className="flex justify-between items-center px-3 py-2">
                      <span className="text-xs text-gray-500">{t('stpm.minimumCGPA')}</span>
                      <span className="text-xs font-medium text-gray-800">{data.requirements.min_cgpa.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center px-3 py-2">
                      <span className="text-xs text-gray-500">{t('stpm.minimumMUET')}</span>
                      <span className="text-xs font-medium text-gray-800">Band {data.requirements.min_muet_band}</span>
                    </div>
                    <div className="flex justify-between items-center px-3 py-2">
                      <span className="text-xs text-gray-500">{t('stpm.minimumSubjects')}</span>
                      <span className="text-xs font-medium text-gray-800">{data.requirements.stpm_min_subjects}</span>
                    </div>
                    <div className="flex justify-between items-center px-3 py-2">
                      <span className="text-xs text-gray-500">{t('stpm.minimumGrade')}</span>
                      <span className="text-xs font-medium text-gray-800">{data.requirements.stpm_min_grade}</span>
                    </div>
                  </div>
                </div>

                {/* STPM Subjects */}
                {data.requirements.stpm_subjects.length > 0 && (
                  <div>
                    <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                      {t('stpm.stpmSubjects')}
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {data.requirements.stpm_subjects.map(subj => (
                        <span key={subj} className="px-2.5 py-1 bg-blue-50 border border-blue-100 rounded-full text-xs font-medium text-blue-700">
                          {subj}
                        </span>
                      ))}
                    </div>
                    {data.requirements.stpm_subject_group && (
                      <p className="text-[11px] text-gray-400 mt-1.5">
                        + flexible subject group requirement
                      </p>
                    )}
                  </div>
                )}

                {/* SPM Prerequisites */}
                {data.requirements.spm_prerequisites.length > 0 && (
                  <div>
                    <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                      {t('stpm.spmPrerequisites')}
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {data.requirements.spm_prerequisites.map(prereq => (
                        <span key={prereq} className="px-2.5 py-1 bg-green-50 border border-green-100 rounded-full text-xs font-medium text-green-700">
                          {prereq}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Special Conditions */}
            <SpecialConditions
              reqInterview={req_interview}
              noColorblind={no_colorblind}
              reqMedicalFitness={req_medical_fitness}
            />

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

function CheckIcon({ color }: { color: 'gray' | 'blue' | 'green' }) {
  const styles = {
    gray: 'bg-gray-100 text-gray-500',
    blue: 'bg-blue-50 text-blue-500',
    green: 'bg-green-50 text-green-500',
  }
  return (
    <span className={`mt-0.5 flex-shrink-0 w-[18px] h-[18px] rounded-full ${styles[color]} flex items-center justify-center`}>
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
      </svg>
    </span>
  )
}
