'use client'

import { type PathwayResult } from '@/lib/pathways'
import { useT } from '@/lib/i18n'

export default function PathwayCards({ results }: { results: PathwayResult[] }) {
  const { t, locale } = useT()

  const matricResults = results.filter(r => r.pathway === 'matric')
  const stpmResults = results.filter(r => r.pathway === 'stpm')
  const anyEligible = results.some(r => r.eligible)

  if (results.length === 0) return null

  function getTrackName(r: PathwayResult): string {
    if (locale === 'ta') return r.trackNameTa
    if (locale === 'ms') return r.trackNameMs
    return r.trackName
  }

  function getReason(r: PathwayResult): string {
    if (!r.reason) return ''
    const translated = t(r.reason)
    if (!r.reasonParams) return translated
    let result = translated
    for (const [key, val] of Object.entries(r.reasonParams)) {
      result = result.replace(`{${key}}`, val)
    }
    return result
  }

  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        {t('pathways.title')}
      </h2>

      {!anyEligible && (
        <p className="text-sm text-gray-500 mb-4">
          {t('pathways.noneEligible')}
        </p>
      )}

      {/* Matriculation */}
      {matricResults.length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">
            {t('pathways.matriculation')}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {matricResults.map(r => (
              <div
                key={r.trackId}
                className={`rounded-xl border p-4 transition-all ${
                  r.eligible
                    ? 'border-green-200 bg-green-50'
                    : 'border-gray-100 bg-gray-50 opacity-60'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">🎓</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {getTrackName(r)}
                  </span>
                </div>
                {r.eligible ? (
                  <>
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 mb-1">
                      {t('pathways.eligible')}
                    </span>
                    <div className="text-xs text-gray-600">
                      {t('pathways.merit')}: <span className="font-bold">{r.merit?.toFixed(1)}</span>/100
                    </div>
                  </>
                ) : (
                  <>
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-500 mb-1">
                      {t('pathways.notEligible')}
                    </span>
                    <div className="text-xs text-gray-400">{getReason(r)}</div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* STPM */}
      {stpmResults.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">
            {t('pathways.stpm')}
          </h3>
          <div className="grid grid-cols-2 gap-3">
            {stpmResults.map(r => (
              <div
                key={r.trackId}
                className={`rounded-xl border p-4 transition-all ${
                  r.eligible
                    ? 'border-blue-200 bg-blue-50'
                    : 'border-gray-100 bg-gray-50 opacity-60'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">📚</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {getTrackName(r)}
                  </span>
                </div>
                {r.eligible ? (
                  <>
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 mb-1">
                      {t('pathways.eligible')}
                    </span>
                    <div className="text-xs text-gray-600">
                      {t('pathways.mataGred')}: <span className="font-bold">{r.mataGred}</span>/{r.maxMataGred}
                    </div>
                  </>
                ) : (
                  <>
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-500 mb-1">
                      {t('pathways.notEligible')}
                    </span>
                    <div className="text-xs text-gray-400">{getReason(r)}</div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
