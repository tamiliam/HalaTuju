'use client'

import { useState, useRef, useEffect } from 'react'
import clsx from 'clsx'

interface FilterPillProps {
  label: string
  value: string
  options: string[]
  optionLabels?: Record<string, string>
  onChange: (value: string) => void
}

export default function FilterPill({
  label,
  value,
  options,
  optionLabels,
  onChange,
}: FilterPillProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close on outside click (same pattern as AppHeader)
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const displayText = value
    ? (optionLabels?.[value] ?? value)
    : label

  const handleSelect = (optionValue: string) => {
    onChange(optionValue)
    setIsOpen(false)
  }

  return (
    <div ref={containerRef} className="relative">
      {/* Pill trigger */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'px-3 py-1.5 text-sm font-medium rounded-full border',
          'flex items-center gap-1.5 transition-colors',
          value
            ? 'border-primary-500 bg-primary-50 text-primary-700 hover:bg-primary-100'
            : 'border-gray-200 bg-gray-100 text-gray-700 hover:bg-gray-200'
        )}
      >
        <span className="max-w-[160px] truncate">{displayText}</span>
        <svg
          className={clsx('w-3.5 h-3.5 shrink-0 transition-transform', isOpen && 'rotate-180')}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown panel */}
      {isOpen && options.length > 0 && (
        <div className="absolute left-0 top-full mt-1 z-20 w-48 max-h-60 overflow-y-auto bg-white rounded-xl shadow-lg border border-gray-200 py-1">
          {/* Reset / "All" option */}
          <button
            type="button"
            onClick={() => handleSelect('')}
            className={clsx(
              'w-full text-left px-4 py-2 text-sm transition-colors',
              !value
                ? 'bg-primary-50 text-primary-600 font-medium'
                : 'text-gray-700 hover:bg-gray-50'
            )}
          >
            {label}
          </button>

          {/* Option items */}
          {options.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => handleSelect(option)}
              className={clsx(
                'w-full text-left px-4 py-2 text-sm transition-colors',
                value === option
                  ? 'bg-primary-50 text-primary-600 font-medium'
                  : 'text-gray-700 hover:bg-gray-50'
              )}
            >
              {optionLabels?.[option] ?? option}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
