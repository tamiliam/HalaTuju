'use client'

import { useEffect, useState } from 'react'

/**
 * A <select> of preset options plus an "Other" choice that reveals a free-text
 * input. Stores a plain string: either a preset's value, or the typed custom text.
 * Used for the reviewer's highest qualification + field of study.
 */
export default function SelectWithOther({
  value, onChange, options, placeholder, otherText, className,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  placeholder: string
  otherText: string
  className?: string
}) {
  const isKnown = (v: string) => options.some((o) => o.value === v)
  const [mode, setMode] = useState<'preset' | 'other'>(value && !isKnown(value) ? 'other' : 'preset')
  // Re-sync when the stored value arrives async and is a non-preset (custom) string.
  useEffect(() => { if (value && !isKnown(value)) setMode('other') }, [value])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-2">
      <select
        value={mode === 'other' ? '__other__' : value}
        onChange={(e) => {
          const v = e.target.value
          if (v === '__other__') { setMode('other'); onChange('') }
          else { setMode('preset'); onChange(v) }
        }}
        className={className}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        <option value="__other__">{otherText}</option>
      </select>
      {mode === 'other' && (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={otherText}
          className={className}
          autoFocus
        />
      )}
    </div>
  )
}
