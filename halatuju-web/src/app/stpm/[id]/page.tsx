'use client'

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { getStpmProgrammeDetail, saveCourse, unsaveCourse } from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'
import { useState } from 'react'

export default function StpmProgrammeDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { t } = useT()
  const [isSaved, setIsSaved] = useState(false)
  const [saving, setSaving] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['stpm_programme', id],
    queryFn: () => getStpmProgrammeDetail(id),
  })

  const handleSave = async () => {
    setSaving(true)
    try {
      if (isSaved) {
        await unsaveCourse(id)
        setIsSaved(false)
      } else {
        await saveCourse(id)
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
          <p className="text-gray-600">Loading programme details...</p>
        </div>
      </main>
    )
  }

  if (error || !data) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Programme not found</h1>
          <p className="text-gray-600 mb-6">{t('courseDetail.notFound')}</p>
          <Link href="/dashboard" className="btn-primary">
            Back to Dashboard
          </Link>
        </div>
      </main>
    )
  }

  const streamLabel = data.stream === 'science' ? 'Science' : data.stream === 'arts' ? 'Arts' : 'Science / Arts'

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      {/* Programme Header */}
      <section className="bg-white border-b">
        <div className="container mx-auto px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-700">
                  Ijazah Sarjana Muda
                </span>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  data.stream === 'science' ? 'bg-green-100 text-green-700' : 'bg-sky-100 text-sky-700'
                }`}>
                  {streamLabel}
                </span>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                {data.program_name}
              </h1>
              <p className="text-lg text-primary-600 font-medium">
                {data.university}
              </p>
            </div>
          </div>
        </div>
      </section>

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
              </section>
            )}

            {/* STPM Subject Requirements */}
            {data.requirements.stpm_subjects.length > 0 && (
              <section className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-3">{t('stpm.stpmSubjects')}</h2>
                <div className="flex flex-wrap gap-2">
                  {data.requirements.stpm_subjects.map(subj => (
                    <span key={subj} className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-full font-medium">
                      {subj}
                    </span>
                  ))}
                </div>
                {data.requirements.stpm_subject_group && (
                  <p className="text-xs text-gray-400 mt-2">
                    + flexible subject group requirement
                  </p>
                )}
              </section>
            )}

            {/* SPM Prerequisites */}
            {data.requirements.spm_prerequisites.length > 0 && (
              <section className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-3">{t('stpm.spmPrerequisites')}</h2>
                <div className="flex flex-wrap gap-2">
                  {data.requirements.spm_prerequisites.map(prereq => (
                    <span key={prereq} className="px-3 py-1 bg-green-50 text-green-700 text-sm rounded-full font-medium">
                      {prereq}
                    </span>
                  ))}
                </div>
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

          {/* Right Column - Quick Info */}
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

            {/* Entry Requirements */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {t('stpm.requirements')}
              </h2>
              <div className="space-y-3">
                <InfoRow label={t('stpm.minimumCGPA')} value={data.requirements.min_cgpa.toFixed(2)} />
                <InfoRow label={t('stpm.minimumMUET')} value={`Band ${data.requirements.min_muet_band}`} />
                <InfoRow label={t('stpm.minimumSubjects')} value={String(data.requirements.stpm_min_subjects)} />
                <InfoRow label={t('stpm.minimumGrade')} value={data.requirements.stpm_min_grade} />
              </div>
            </section>

            {/* Flags */}
            {(data.requirements.req_interview ||
              data.requirements.no_colorblind ||
              data.requirements.req_medical_fitness ||
              data.requirements.req_malaysian ||
              data.requirements.req_bumiputera) && (
              <section className="bg-white rounded-xl border border-gray-200 p-6">
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
                </div>
              </section>
            )}

            {/* Actions */}
            <section className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {t('courseDetail.actions')}
              </h2>
              <div className="space-y-3">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="btn-primary w-full"
                >
                  {isSaved ? t('courseDetail.removeFromSaved') : t('courseDetail.saveCourse')}
                </button>
                <Link
                  href="/dashboard"
                  className="btn-secondary w-full text-center block"
                >
                  {t('courseDetail.backToRecommendations')}
                </Link>
              </div>
            </section>
          </div>
        </div>
      </div>

      <AppFooter />
    </main>
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
