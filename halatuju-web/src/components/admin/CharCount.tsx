import type { ReactNode } from 'react'

/** The character count under a text box: right-aligned, directly beneath it, on its own line.
 *  ONE placement for every admin form that counts (the reviewer notes card, the reject form). The caller
 *  keeps its own wording and limits, and tints the text (`className`) when over. */
export function CharCount({ id, className = 'text-ground-600', testId, children }: {
  id: string
  className?: string
  testId?: string
  children: ReactNode
}) {
  return (
    <p id={id} aria-live="polite" data-testid={testId} className={`text-right text-xs whitespace-nowrap ${className}`}>
      {children}
    </p>
  )
}
