'use client'

import { useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import type { EligibleCourse } from '@/lib/api'
import type { ChosenProgramme } from '@/lib/scholarship'

/**
 * Single-select course picker for the B40 apply form's "decided" branch. Lists ONLY
 * the courses the student is eligible for on the chosen pathway (passed in already
 * filtered + sorted A–Z), as a type-to-search combobox (same UX as the School field).
 * Selection is constrained to the list — there is no free-text fallback, because the
 * whole point is that they pick one eligible course. The query is local; the parent's
 * `value` is the source of truth, so on blur the input snaps back to the selection.
 *
 * Loading + empty states are handled here so the parent stays declarative.
 */
export default function ProgrammePicker({
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
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(value?.courseName ?? '')
  const [active, setActive] = useState(-1)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  if (loading) {
    return (
      <input className="input text-gray-400" disabled value={t('scholarship.apply.plan.loading')} readOnly />
    )
  }
  if (courses.length === 0) {
    return (
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-gray-600">
        {t('scholarship.apply.plan.noProgrammes')}
      </p>
    )
  }

  const q = query.trim().toLowerCase()
  const matches = q ? courses.filter((c) => c.course_name.toLowerCase().includes(q)) : courses

  const choose = (c: EligibleCourse) => {
    onChange({ courseId: c.course_id, courseName: c.course_name, fieldKey: c.field_key || c.field || '' })
    setQuery(c.course_name)
    setOpen(false)
    setActive(-1)
  }

  return (
    <div className="relative">
      <input
        className="input"
        value={query}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        placeholder={t('scholarship.apply.plan.programmePlaceholder')}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(-1) }}
        onFocus={() => setOpen(true)}
        // Snap the input back to the committed selection — typing only searches; it
        // never changes the value unless a course is actually clicked.
        onBlur={() => { blurTimer.current = setTimeout(() => { setOpen(false); setQuery(value?.courseName ?? '') }, 120) }}
        onKeyDown={(e) => {
          if (!open || matches.length === 0) return
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, matches.length - 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
          else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(matches[active]) }
          else if (e.key === 'Escape') { setOpen(false); setActive(-1) }
        }}
      />
      {open && (
        <div
          className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg"
          onMouseDown={(e) => e.preventDefault()}
        >
          {matches.length > 0 ? (
            <ul className="max-h-64 overflow-auto py-1" role="listbox">
              {matches.map((c, i) => (
                <li key={c.course_id} role="option" aria-selected={i === active}>
                  <button
                    type="button"
                    onClick={() => choose(c)}
                    onMouseEnter={() => setActive(i)}
                    className={`flex w-full flex-col items-start px-3 py-2 text-left text-sm ${i === active ? 'bg-primary-50' : 'hover:bg-gray-50'}`}
                  >
                    <span className="text-gray-900">{c.course_name}</span>
                    {c.institution_name && (
                      <span className="text-xs text-gray-400">
                        {c.institution_count && c.institution_count > 1
                          ? t('scholarship.apply.plan.programmeAtN', { n: String(c.institution_count) })
                          : c.institution_name}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-2 text-xs text-gray-500">{t('scholarship.apply.plan.programmeNoMatch')}</p>
          )}
        </div>
      )}
    </div>
  )
}
