'use client'

import { useT } from '@/lib/i18n'

export interface PathwaySummary {
  type: 'asasi' | 'pismp' | 'poly' | 'university' | 'kkom' | 'iljtm' | 'ilkbs' | 'mara' | 'tvet_other' | 'matric' | 'stpm'
  label: string
  count?: number
  eligible: boolean
}

export default function PathwayCards({
  pathways,
  activeFilter,
  onFilterChange,
}: {
  pathways: PathwaySummary[]
  activeFilter: string
  onFilterChange: (type: string) => void
}) {
  const { t } = useT()

  const eligible = pathways.filter(p => p.eligible)

  if (eligible.length === 0) return null

  return (
    <div className="mb-4 border-b border-ground-100 pb-4 md:border-0 md:pb-0">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-semibold text-ground-700">{t('pathways.title')}:</span>
        {eligible.map(p => {
          const isActive = activeFilter === p.type
          return (
            <button
              key={p.type}
              onClick={() => onFilterChange(isActive ? 'all' : p.type)}
              className={`inline-flex min-h-11 items-center gap-1 rounded-full px-3.5 text-sm font-medium transition-colors cursor-pointer md:min-h-0 md:px-2.5 md:py-0.5 md:text-xs ${
                isActive
                  ? 'bg-brand-fill text-brand-fill-ink border border-primary-600'
                  : 'bg-primary-50 text-primary-700 border border-primary-200 hover:bg-primary-100'
              }`}
            >
              {p.label}
              {p.count != null && (
                <span className={isActive ? 'text-primary-200' : 'text-primary-400'}>{p.count}</span>
              )}
            </button>
          )
        })}
        {activeFilter !== 'all' && (
          <button
            onClick={() => onFilterChange('all')}
            className="inline-flex min-h-11 items-center px-2 text-xs text-ground-400 hover:text-ground-600 md:min-h-0 md:px-0 md:ml-1"
          >
            {t('dashboard.clearFilter')}
          </button>
        )}
      </div>
    </div>
  )
}
