'use client'

// Bidang (subject) chooser for the PISMP pathway — the second tap, shown once a school
// type (Aliran) is picked. An in-card tappable list of the eligible bidang for that
// aliran; selecting one commits the exact PISMP course as the chosen programme. The
// bidang label is the course name minus its school-type suffix. i18n reuses the
// `scholarship.apply.plan.bidang*` keys.
import { useT } from '@/lib/i18n'
import type { EligibleCourse } from '@/lib/api'
import { bidangLabel, type ChosenProgramme } from '@/lib/scholarship'

export default function BidangPicker({
  courses,
  value,
  onChange,
  loading = false,
}: {
  courses: EligibleCourse[]
  value: ChosenProgramme | null
  onChange: (programme: ChosenProgramme | null) => void
  loading?: boolean
}) {
  const { t } = useT()

  if (loading) {
    return <p className="text-sm text-gray-400">{t('scholarship.apply.plan.loading')}</p>
  }
  if (courses.length === 0) {
    return (
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-gray-600">
        {t('scholarship.apply.plan.noProgrammes')}
      </p>
    )
  }

  const choose = (c: EligibleCourse) =>
    onChange({ courseId: c.course_id, courseName: c.course_name, fieldKey: c.field_key || c.field || '' })

  return (
    <div>
      <p className="mb-2 text-xs text-gray-500">
        {t('scholarship.apply.plan.bidangCount', { n: String(courses.length) })}
      </p>
      <ul className="divide-y divide-gray-100 overflow-hidden rounded-xl border border-gray-200" role="listbox">
        {courses.map((c) => {
          const on = value?.courseId === c.course_id
          return (
            <li key={c.course_id} role="option" aria-selected={on}>
              <button
                type="button"
                onClick={() => choose(c)}
                className={`flex w-full items-center justify-between px-3 py-3 text-left text-sm ${
                  on ? 'bg-primary-50 font-medium text-primary-700' : 'text-gray-800 hover:bg-gray-50'
                }`}
              >
                <span className="flex items-center gap-2">
                  {on && <span aria-hidden className="text-primary-600">✓</span>}
                  {bidangLabel(c.course_name)}
                </span>
                {!on && <span aria-hidden className="text-gray-300">›</span>}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
