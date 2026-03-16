'use client'

import { type MascoOccupation } from '@/lib/api'
import { useT } from '@/lib/i18n'

interface CareerPathwaysProps {
  occupations: MascoOccupation[]
}

export default function CareerPathways({ occupations }: CareerPathwaysProps) {
  const { t } = useT()

  if (!occupations || occupations.length === 0) return null

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-2">
        {t('courseDetail.careerPathways')}
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        {t('courseDetail.careerPathwaysDesc')}
      </p>
      <div className="flex flex-wrap gap-2">
        {occupations.map((occ) =>
          occ.emasco_url ? (
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
          ) : (
            <span
              key={occ.masco_code}
              className="inline-flex items-center px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium"
            >
              {occ.job_title}
            </span>
          )
        )}
      </div>
    </section>
  )
}
