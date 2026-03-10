'use client'

import { type PathwayResult } from '@/lib/pathways'
import { useT } from '@/lib/i18n'

function GraduationCapIcon() {
  return (
    <svg className="w-5 h-5 text-primary-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15v-3.75m0 0 5.25 3 5.25-3" />
    </svg>
  )
}

function BookOpenIcon() {
  return (
    <svg className="w-5 h-5 text-primary-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
    </svg>
  )
}

export default function PathwayCards({ results }: { results: PathwayResult[] }) {
  const { t, locale } = useT()

  const eligible = results.filter(r => r.eligible)

  if (eligible.length === 0) return null

  function getTitle(r: PathwayResult): string {
    const name = locale === 'ta' ? r.trackNameTa : locale === 'ms' ? r.trackNameMs : r.trackName
    if (r.pathway === 'matric') {
      return locale === 'ms' ? `Matrikulasi — ${name}` : locale === 'ta' ? `மெட்ரிக் — ${name}` : `Matriculation — ${name}`
    }
    return locale === 'ms' ? `Tingkatan 6 — ${name}` : locale === 'ta' ? `படிவம் 6 — ${name}` : `Form 6 — ${name}`
  }

  function getScore(r: PathwayResult): string {
    if (r.pathway === 'matric') {
      return `${t('pathways.merit')}: ${r.merit?.toFixed(1)}/100`
    }
    return `${t('pathways.mataGred')}: ${r.mataGred}/${r.maxMataGred}`
  }

  return (
    <div className="mb-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">
        {t('pathways.title')}
      </h2>
      <div className="flex flex-wrap gap-3">
        {eligible.map(r => (
          <div
            key={`${r.pathway}-${r.trackId}`}
            className="flex items-center gap-3 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow px-4 py-3"
          >
            {r.pathway === 'matric' ? <GraduationCapIcon /> : <BookOpenIcon />}
            <div className="min-w-0">
              <div className="text-sm font-semibold text-gray-900 leading-tight">
                {getTitle(r)}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="inline-block px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-green-100 text-green-700">
                  {t('pathways.eligible')}
                </span>
                <span className="text-xs text-gray-500">{getScore(r)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
