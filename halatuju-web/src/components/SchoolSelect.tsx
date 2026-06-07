'use client'

import { useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import { searchSchools } from '@/data/secondary-schools'

/**
 * Searchable School field for the B40 apply form. Suggests matches from the MOE
 * secondary-school list as the student types, but the typed text is always the
 * value — so a school that isn't listed (or is spelled differently) is never
 * blocked. Selecting a suggestion fills in its official name.
 */
export default function SchoolSelect({
  value,
  onChange,
  maxLength = 255,   // mirrors StudentProfile.school varchar(255) so a typed name can't overflow
}: {
  value: string
  onChange: (v: string) => void
  maxLength?: number
}) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const matches = open ? searchSchools(value) : []
  const showPanel = open && value.trim().length >= 2
  const exact = matches.some((m) => m.name.toLowerCase() === value.trim().toLowerCase())

  const choose = (name: string) => {
    onChange(name)
    setOpen(false)
    setActive(-1)
  }

  return (
    <div className="relative">
      <input
        className="input"
        maxLength={maxLength}
        value={value}
        autoComplete="off"
        role="combobox"
        aria-expanded={showPanel}
        aria-autocomplete="list"
        placeholder={t('scholarship.apply.schoolSearchPlaceholder')}
        onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(-1) }}
        onFocus={() => setOpen(true)}
        onBlur={() => { blurTimer.current = setTimeout(() => setOpen(false), 120) }}
        onKeyDown={(e) => {
          if (!showPanel || matches.length === 0) return
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, matches.length - 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
          else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(matches[active].name) }
          else if (e.key === 'Escape') { setOpen(false); setActive(-1) }
        }}
      />
      {showPanel && (
        // preventDefault on mousedown keeps the input focused so the button's
        // onClick fires before the input's onBlur closes the panel.
        <div
          className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg"
          onMouseDown={(e) => e.preventDefault()}
        >
          {matches.length > 0 ? (
            <ul className="max-h-64 overflow-auto py-1" role="listbox">
              {matches.map((s, i) => (
                <li key={s.code} role="option" aria-selected={i === active}>
                  <button
                    type="button"
                    onClick={() => choose(s.name)}
                    onMouseEnter={() => setActive(i)}
                    className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm ${i === active ? 'bg-primary-50' : 'hover:bg-gray-50'}`}
                  >
                    <span className="text-gray-900">{s.name}</span>
                    <span className="shrink-0 text-xs text-gray-400">{s.state}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-2 text-xs text-gray-500">{t('scholarship.apply.schoolNoMatch')}</p>
          )}
          {!exact && (
            <p className="border-t border-gray-100 px-3 py-2 text-xs text-gray-400">
              {t('scholarship.apply.schoolNotListed')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
