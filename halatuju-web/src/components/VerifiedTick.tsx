'use client'

import { useEffect, useRef, useState } from 'react'

/**
 * A very small, non-obtrusive "verified" badge (the FB/X seal-check) shown after a field value
 * whose typed value has been MATCHED against an uploaded, machine-read document. Monochrome +
 * ~14px so it sits quietly beside the value; the `label` names WHAT it was matched against (e.g.
 * "Matches MyKad"). Absence of the tick means "not corroborated" — we never render a red/failed
 * state here (the Documents drawer owns mismatches).
 *
 * ⚠ THE LABEL IS REACHABLE BY TAP (Mobile M1a, mobile-standard.md rule 4). It used to live in
 * `title` only — a hover tooltip, which a phone never shows, so on a reviewer's phone the tick
 * explained nothing. The seal is now a button: a tap (or click, or Enter) shows the label in a
 * small bubble, closed by a second tap, a tap elsewhere, Escape or moving focus on. Its target is
 * 44 px; -15 px margins cancel the padding, so the 14 px seal sits exactly where it did. The
 * `title` stays for a desktop mouse. No hover handler, so a tap's compatibility mouseenter cannot
 * open-and-shut it (the defect InfoTip had). Not built on InfoTip on purpose: that one ships on
 * the student routes, which sit on their first-load lines; this one only on the officer's.
 */
export default function VerifiedTick({ label }: { label: string }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false) }
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return (
    <span ref={root} className="relative ml-1 inline-flex shrink-0 align-middle">
      <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)}
        onBlur={() => setOpen(false)} className="-m-[15px] inline-flex p-[15px]">
        <span title={label} aria-label={label} role="img" className="inline-flex text-info-600">
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" aria-hidden>
            <path
              fill="currentColor"
              d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"
            />
            {/* `stroke-white` (a literal), never `--ground-0`: this tick sits ON the coloured seal,
                so it must NOT invert with the ground — the same rule the codemod applies to
                `text-white`. It was a raw `#fff`, which a class scan cannot see. */}
            <path
              d="m9 12 2 2 4-4"
              fill="none"
              className="stroke-white"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>
      {open && (
        // Anchored to the RIGHT of the seal: a tick trails its value, so the bubble opens back over
        // the value rather than off the right edge of a phone.
        <span role="tooltip"
          className="absolute right-0 top-5 z-30 w-max max-w-[14rem] rounded-lg border border-info-100 bg-ground-0 px-2.5 py-1.5 text-xs font-normal normal-case tracking-normal text-ground-700 shadow-lg">
          {label}
        </span>
      )}
    </span>
  )
}
