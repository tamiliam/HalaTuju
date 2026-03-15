'use client'

import { useState } from 'react'
import { formatIc, validateIc } from '@/lib/ic-utils'

interface IcInputProps {
  value: string
  onChange: (digits: string) => void
  onValidChange?: (isValid: boolean) => void
  error?: string | null
  label?: string
  placeholder?: string
  disabled?: boolean
}

export default function IcInput({
  value,
  onChange,
  onValidChange,
  error: externalError,
  label,
  placeholder = 'XXXXXX-XX-XXXX',
  disabled = false,
}: IcInputProps) {
  const [touched, setTouched] = useState(false)

  const formatted = formatIc(value)
  const validationError = touched && value.length > 0 ? validateIc(value) : null
  const displayError = externalError || validationError

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Extract only digits from the input
    const raw = e.target.value.replace(/\D/g, '').slice(0, 12)
    onChange(raw)

    if (onValidChange) {
      onValidChange(raw.length === 12 && validateIc(raw) === null)
    }
  }

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label} <span className="text-red-500">*</span>
        </label>
      )}
      <input
        type="text"
        inputMode="numeric"
        value={formatted}
        onChange={handleChange}
        onBlur={() => setTouched(true)}
        placeholder={placeholder}
        disabled={disabled}
        className={`w-full px-3 py-2.5 border rounded-lg text-sm tracking-wider focus:ring-1 outline-none ${
          displayError
            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:border-primary-500 focus:ring-primary-500'
        }`}
      />
      {displayError && (
        <p className="mt-1 text-xs text-red-500">{displayError}</p>
      )}
    </div>
  )
}
