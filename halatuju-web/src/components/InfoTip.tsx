'use client'

import { useState } from 'react'

/**
 * A friendly `i` help bubble. Tap/click toggles a small popover that works on
 * both mobile and desktop. Used across the B40 apply form to explain fields.
 * Styled on-brand (primary tint, white card, caret + helper icon) rather than
 * the old flat grey/dark tooltip.
 */
export default function InfoTip({ text, defaultOpen = false }: { text: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    // Hover (desktop) and click/tap (mobile) both open the SAME custom popover.
    // No native `title` — that produced a second, drab browser tooltip on hover.
    <span
      className="relative inline-flex align-middle"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button" aria-label={text}
        onClick={() => setOpen((v) => !v)} onBlur={() => setOpen(false)}
        className="ml-1 inline-flex h-[18px] w-[18px] items-center justify-center rounded-full bg-primary-100 text-[11px] font-bold leading-none text-primary-700 ring-1 ring-inset ring-primary-200 transition-colors hover:bg-primary-200 hover:text-primary-800"
      >
        i
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-1/2 top-7 z-30 w-64 -translate-x-1/2 rounded-xl border border-primary-100 bg-white px-3.5 py-3 text-left text-xs font-normal leading-relaxed text-gray-600 shadow-xl"
        >
          {/* caret pointing up at the i button */}
          <span className="absolute -top-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-l border-t border-primary-100 bg-white" />
          <span className="relative flex gap-2">
            <svg className="mt-0.5 h-4 w-4 shrink-0 text-primary-500" fill="none" stroke="currentColor" strokeWidth={1.7} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.5 17h5M10 20.5h4M12 3a6 6 0 00-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0012 3z" />
            </svg>
            <span>{text}</span>
          </span>
        </span>
      )}
    </span>
  )
}
