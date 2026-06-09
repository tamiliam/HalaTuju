'use client'

import { useRef, useState } from 'react'
import { useT } from '@/lib/i18n'

export interface InstitutionOption {
  name: string
  hint?: string       // secondary text, e.g. state or acronym
  keywords?: string   // extra searchable text (acronyms, aliases) — matched, not shown
}

/**
 * Single-select institution combobox for the B40 apply form's institution pathways
 * (P4) — reused for both the matriculation college list and the 584 STPM centres.
 * Options are passed in already narrowed (by track / by stream); the component does
 * type-to-search over them and stores the chosen name (a string). Same constrained
 * UX as ProgrammePicker: typing only searches, blur snaps back to the selection.
 * The rendered list is capped so a large stream list stays light until the user types.
 */
export default function InstitutionPicker({
  options,
  value,
  onChange,
  placeholder,
  limit = 50,
  allowCustom = false,
}: {
  options: InstitutionOption[]
  value: string
  onChange: (name: string) => void
  placeholder?: string
  limit?: number
  // When true, a typed value with no match is kept (free text) on blur — for
  // private/foreign/unknown entries. When false (default), blur snaps back to the
  // current selection (the constrained apply-form behaviour).
  allowCustom?: boolean
}) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(value ?? '')
  const [active, setActive] = useState(-1)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const q = query.trim().toLowerCase()
  const filtered = q
    ? options.filter((o) => `${o.name} ${o.keywords ?? ''}`.toLowerCase().includes(q))
    : options
  const matches = filtered.slice(0, limit)
  const truncated = filtered.length > matches.length

  const choose = (name: string) => {
    onChange(name)
    setQuery(name)
    setOpen(false)
    setActive(-1)
  }

  return (
    <div className="relative">
      <input
        className="input"
        value={query}
        // Chrome ignores autoComplete="off" for fields it guesses are address/contact
        // (school/college names trigger this readily) and pops its saved-address list over
        // ours. "new-password" suppresses that; data-*ignore mute 1Password/LastPass.
        autoComplete="new-password"
        data-1p-ignore
        data-lpignore="true"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        placeholder={placeholder ?? t('scholarship.apply.plan.schoolPlaceholder')}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(-1) }}
        onFocus={() => setOpen(true)}
        onBlur={() => { blurTimer.current = setTimeout(() => {
          setOpen(false)
          if (allowCustom) { const v = query.trim(); if (v !== value) onChange(v) }
          else setQuery(value ?? '')
        }, 120) }}
        onKeyDown={(e) => {
          if (!open || matches.length === 0) return
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, matches.length - 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
          else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(matches[active].name) }
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
              {matches.map((o, i) => (
                <li key={o.name} role="option" aria-selected={i === active}>
                  <button
                    type="button"
                    onClick={() => choose(o.name)}
                    onMouseEnter={() => setActive(i)}
                    className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm ${i === active ? 'bg-primary-50' : 'hover:bg-gray-50'}`}
                  >
                    <span className="text-gray-900">{o.name}</span>
                    {o.hint && <span className="shrink-0 text-xs text-gray-400">{o.hint}</span>}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-2 text-xs text-gray-500">{t('scholarship.apply.plan.institutionNoMatch')}</p>
          )}
          {truncated && (
            <p className="border-t border-gray-100 px-3 py-2 text-xs text-gray-400">
              {t('scholarship.apply.plan.institutionMore')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
