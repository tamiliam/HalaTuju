'use client'

import { TYPE_LABELS, institutionTypeChip, LEVEL_CHIP } from '@/lib/courseBadges'
import { PHONE_GUTTER } from '@/lib/phoneSection'

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
    <section className="bg-ground-0 border-b">
      <div className={`container mx-auto ${PHONE_GUTTER} py-5 md:py-8`}>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-1.5 mb-3">
              <span
                className={`px-2.5 py-1 rounded text-xs font-medium ${institutionTypeChip(typeKey)}`}
              >
                {TYPE_LABELS[typeKey] || sourceType}
              </span>
              {level && (
                <span
                  className={`px-2.5 py-1 rounded text-xs font-medium ${LEVEL_CHIP}`}
                >
                  {level}
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-ground-900 mb-2 md:text-3xl">
              {title}
            </h1>
            {subtitle && (
              <p className="text-base text-primary-600 font-medium md:text-lg">
                {subtitle}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
