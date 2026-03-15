'use client'

import { TYPE_LABELS, TYPE_COLORS, LEVEL_COLORS } from '@/lib/courseBadges'

interface CourseHeaderProps {
  sourceType: string
  pathwayType?: string
  level: string
  title: string
  subtitle?: string
}

export default function CourseHeader({ sourceType, pathwayType, level, title, subtitle }: CourseHeaderProps) {
  const typeKey = pathwayType || sourceType

  return (
    <section className="bg-white border-b">
      <div className="container mx-auto px-6 py-8">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-1.5 mb-3">
              <span
                className={`px-2.5 py-1 rounded text-xs font-medium ${
                  TYPE_COLORS[typeKey] || 'bg-gray-100 text-gray-700'
                }`}
              >
                {TYPE_LABELS[typeKey] || sourceType}
              </span>
              {level && (
                <span
                  className={`px-2.5 py-1 rounded text-xs font-medium ${
                    LEVEL_COLORS[level] || 'bg-gray-50 text-gray-600'
                  }`}
                >
                  {level}
                </span>
              )}
            </div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {title}
            </h1>
            {subtitle && (
              <p className="text-lg text-primary-600 font-medium">
                {subtitle}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
