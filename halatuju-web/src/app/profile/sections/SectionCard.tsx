import type { ReactNode } from 'react'
import { useT } from '@/lib/i18n'
import { PHONE_SECTION_NO_GAP } from '@/lib/phoneSection'

/** Rule 15 (Mobile M4b): a section's read-only rows, divided by hairlines on a phone (never boxed). */
export const PROFILE_ROWS = 'max-md:divide-y max-md:divide-ground-100 max-md:[&>*]:py-2.5'   // phones only: md+ keeps its own borders and spacing

/**
 * One /profile section's frame: the icon tile, the title, the "N incomplete" badge and the Edit
 * button. A3.9: the five copies of this header in the old page, moved here unchanged.
 */
export default function SectionCard({ title, incomplete, icon, canEdit, onEdit, children }: {
  title: string
  incomplete: number
  icon: ReactNode
  canEdit: boolean
  onEdit: () => void
  children: ReactNode
}) {
  const { t } = useT()
  return (
    <div className={`${PHONE_SECTION_NO_GAP} md:mb-5 ${incomplete > 0 ? 'md:border-l-4 md:border-l-amber-400' : ''}`}>
      <div className="flex items-center justify-between gap-2 mb-1 md:mb-5">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <div className="hidden w-10 h-10 rounded-lg bg-gradient-to-br from-brand-fill to-brand-fill-hover md:flex items-center justify-center shadow-sm shadow-primary-500/20">
            <svg className="w-5 h-5 text-brand-fill-ink" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              {icon}
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-ground-900">{title}</h2>
          {incomplete > 0 && (
            <span className="px-2 py-0.5 bg-caution-50 text-caution-700 text-xs font-medium rounded-full">
              {incomplete} {t('profile.incomplete')}
            </span>
          )}
        </div>
        {canEdit && (
          <button onClick={onEdit} className="-mr-2 inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center px-2 text-sm text-primary-600 hover:text-primary-700 font-medium">
            {t('profile.edit')}
          </button>
        )}
      </div>
      {children}
    </div>
  )
}
