'use client'

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { getStpmProgrammeDetail } from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function StpmProgrammeDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { t } = useT()

  const { data, isLoading, error } = useQuery({
    queryKey: ['stpm_programme', id],
    queryFn: () => getStpmProgrammeDetail(id),
  })

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader />
      <div className="container mx-auto px-6 py-8 flex-1">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-sm text-gray-500">
          <Link href="/dashboard" className="hover:text-primary-500">Dashboard</Link>
          <span>&rsaquo;</span>
          <Link href="/stpm/search" className="hover:text-primary-500">{t('stpm.searchTitle')}</Link>
          <span>&rsaquo;</span>
          <span className="text-gray-900">{t('stpm.programmeDetail')}</span>
        </div>

        {isLoading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          </div>
        ) : error || !data ? (
          <div className="text-center py-12">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Programme not found</h2>
            <Link href="/stpm/search" className="text-primary-500 hover:text-primary-600">
              &larr; {t('stpm.backToResults')}
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main content */}
            <div className="lg:col-span-2 space-y-6">
              {/* Header */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-start gap-3 mb-3">
                  <span className="px-2 py-0.5 bg-purple-50 text-purple-700 text-xs font-medium rounded-full">
                    {t(`stpm.${data.stream}`)}
                  </span>
                </div>
                <h1 className="text-xl font-bold text-gray-900 mb-2">{data.program_name}</h1>
                <p className="text-gray-500">{data.university}</p>
              </div>

              {/* STPM Subject Requirements */}
              {data.requirements.stpm_subjects.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <h2 className="font-semibold text-gray-900 mb-3">{t('stpm.stpmSubjects')}</h2>
                  <div className="flex flex-wrap gap-2">
                    {data.requirements.stpm_subjects.map(subj => (
                      <span key={subj} className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-full">
                        {subj}
                      </span>
                    ))}
                  </div>
                  {data.requirements.stpm_subject_group && (
                    <p className="text-xs text-gray-400 mt-2">
                      + flexible subject group requirement
                    </p>
                  )}
                </div>
              )}

              {/* SPM Prerequisites */}
              {data.requirements.spm_prerequisites.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <h2 className="font-semibold text-gray-900 mb-3">{t('stpm.spmPrerequisites')}</h2>
                  <div className="flex flex-wrap gap-2">
                    {data.requirements.spm_prerequisites.map(prereq => (
                      <span key={prereq} className="px-3 py-1 bg-green-50 text-green-700 text-sm rounded-full">
                        {prereq}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Quick Facts */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="font-semibold text-gray-900 mb-4">{t('stpm.requirements')}</h2>
                <dl className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">{t('stpm.minimumCGPA')}</dt>
                    <dd className="font-medium text-gray-900">{data.requirements.min_cgpa.toFixed(2)}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">{t('stpm.minimumMUET')}</dt>
                    <dd className="font-medium text-gray-900">Band {data.requirements.min_muet_band}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">{t('stpm.minimumSubjects')}</dt>
                    <dd className="font-medium text-gray-900">{data.requirements.stpm_min_subjects}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">{t('stpm.minimumGrade')}</dt>
                    <dd className="font-medium text-gray-900">{data.requirements.stpm_min_grade}</dd>
                  </div>
                </dl>
              </div>

              {/* Flags */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="space-y-2">
                  {data.requirements.req_interview && (
                    <div className="flex items-center gap-2 text-sm text-amber-700">
                      <span className="w-2 h-2 bg-amber-500 rounded-full" />
                      {t('stpm.interviewRequired')}
                    </div>
                  )}
                  {data.requirements.no_colorblind && (
                    <div className="flex items-center gap-2 text-sm text-red-700">
                      <span className="w-2 h-2 bg-red-500 rounded-full" />
                      {t('stpm.noColorblind')}
                    </div>
                  )}
                  {data.requirements.req_medical_fitness && (
                    <div className="flex items-center gap-2 text-sm text-orange-700">
                      <span className="w-2 h-2 bg-orange-500 rounded-full" />
                      {t('stpm.medicalFitness')}
                    </div>
                  )}
                  {data.requirements.req_malaysian && (
                    <div className="flex items-center gap-2 text-sm text-gray-700">
                      <span className="w-2 h-2 bg-gray-500 rounded-full" />
                      {t('stpm.malaysianOnly')}
                    </div>
                  )}
                  {data.requirements.req_bumiputera && (
                    <div className="flex items-center gap-2 text-sm text-gray-700">
                      <span className="w-2 h-2 bg-gray-500 rounded-full" />
                      {t('stpm.bumiputeraOnly')}
                    </div>
                  )}
                  {!data.requirements.req_interview &&
                   !data.requirements.no_colorblind &&
                   !data.requirements.req_medical_fitness &&
                   !data.requirements.req_malaysian &&
                   !data.requirements.req_bumiputera && (
                    <p className="text-sm text-gray-400">No special requirements</p>
                  )}
                </div>
              </div>

              {/* Back link */}
              <Link
                href="/stpm/search"
                className="block text-center py-3 text-primary-600 hover:text-primary-700 text-sm font-medium"
              >
                &larr; {t('stpm.backToResults')}
              </Link>
            </div>
          </div>
        )}
      </div>
      <AppFooter />
    </div>
  )
}
