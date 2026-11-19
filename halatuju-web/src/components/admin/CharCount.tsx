import type { ReactNode } from 'react'

/** The character count under a text box: right-aligned, directly beneath it, on its own line.
 *  ONE placement for every admin form that counts (the reviewer notes card, the reject form). The caller
 *  keeps its own wording and limits, and tints the text (`className`) when over. `live` makes it a polite
 *  live region (the notes card, as before); off by default so a screen reader is not read the count on every
 *  keystroke (the box's aria-describedby already points at it). */
export function CharCount({ id, className = 'text-ground-600', testId, live = false, children }: {
  id: string
  className?: string
  testId?: string
  live?: boolean
  children: ReactNode
}) {
  return (
    <p id={id} aria-live={live ? 'polite' : undefined} data-testid={testId} className={`text-right text-xs whitespace-nowrap ${className}`}>
      {children}
    </p>
  )
}
