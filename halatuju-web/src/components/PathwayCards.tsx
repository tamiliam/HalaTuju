'use client'

import { useT } from '@/lib/i18n'

export interface PathwaySummary {
  type: 'asasi' | 'pismp' | 'poly' | 'ua' | 'kkom' | 'iljtm' | 'ilkbs' | 'matric' | 'stpm'
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
    <div className="mb-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-semibold text-gray-700">{t('pathways.title')}:</span>
        {eligible.map(p => {
          const isActive = activeFilter === p.type
          return (
            <button
              key={p.type}
              onClick={() => onFilterChange(isActive ? 'all' : p.type)}
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors cursor-pointer ${
                isActive
                  ? 'bg-primary-600 text-white border border-primary-600'
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
            className="text-xs text-gray-400 hover:text-gray-600 ml-1"
          >
            {t('dashboard.clearFilter')}
          </button>
        )}
      </div>
    </div>
  )
}
