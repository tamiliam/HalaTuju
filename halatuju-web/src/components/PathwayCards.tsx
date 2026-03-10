'use client'

import { useT } from '@/lib/i18n'

export interface PathwaySummary {
  type: 'asasi' | 'matric' | 'stpm' | 'pismp' | 'poly' | 'university' | 'kkom' | 'iljtm' | 'ilkbs'
  label: string
  count?: number
  eligible: boolean
  detail?: string
}

export default function PathwayCards({ pathways }: { pathways: PathwaySummary[] }) {
  const { t } = useT()

  const eligible = pathways.filter(p => p.eligible)

  if (eligible.length === 0) return null

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-semibold text-gray-700">{t('pathways.title')}:</span>
        {eligible.map(p => (
          <span
            key={p.type}
            className="inline-flex items-center gap-1 rounded-full bg-primary-50 border border-primary-200 px-2.5 py-0.5 text-xs font-medium text-primary-700"
          >
            {p.label}
            {p.count != null && (
              <span className="text-primary-400">{p.count}</span>
            )}
            {p.detail && (
              <span className="text-primary-400">{p.detail}</span>
            )}
          </span>
        ))}
      </div>
    </div>
  )
}
