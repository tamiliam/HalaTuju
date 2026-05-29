'use client'

/**
 * Standard messaging-box for forms across /application (and beyond).
 * Four semantic colours, locked palette + sizing so every "this is a note"
 * across the site looks the same.
 *
 *   <InfoBox kind="success">Saved.</InfoBox>
 *   <InfoBox kind="info">Heads-up: …</InfoBox>
 *   <InfoBox kind="warning">Please upload your IC first.</InfoBox>
 *   <InfoBox kind="block">Could not save. Try again.</InfoBox>
 *
 * For top-of-card section banners (larger), don't use this — those have
 * their own `rounded-xl p-5` style (see ScholarshipNextSteps intro banner).
 */

type Kind = 'success' | 'info' | 'warning' | 'block'

const PALETTE: Record<Kind, string> = {
  // bg-{c}-50 / border-{c}-200 / text-{c}-800 across all four — tested for
  // accessible contrast on the light-mode background.
  success: 'border-green-200 bg-green-50 text-green-800',
  info:    'border-blue-200 bg-blue-50 text-blue-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  block:   'border-red-200 bg-red-50 text-red-800',
}

export default function InfoBox({
  kind,
  children,
  className = '',
}: {
  kind: Kind
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={`rounded-lg border p-3 text-sm ${PALETTE[kind]} ${className}`}>
      {children}
    </div>
  )
}
