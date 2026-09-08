'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useT } from '@/lib/i18n'

/** THE ONE SHELL EVERY CONSOLE TABLE SITS IN (owner, 2026-09-08).
 *
 *  Fourteen tables were built fourteen times, and on a phone they behaved three different ways:
 *  six scrolled properly, five squashed their columns into slivers because they had no minimum
 *  width, and TWO — Intake years and Course data — were CLIPPED by their own card with no
 *  scrollbar at all, so the right-hand columns were simply gone. Nothing told anybody which of the
 *  three they were looking at.
 *
 *  ⚠ THE PROMISE THIS COMPONENT KEEPS, and why each half is load-bearing:
 *
 *  1. **A table never clips.** The card carries `overflow-hidden` only for its rounded corners;
 *     the SCROLLING layer is a separate div inside it. Those two must not be the same element —
 *     that single mistake is what cut Intake years off.
 *  2. **Columns keep their shape.** `minWidth` is a floor, not a suggestion. Without it a table
 *     shrinks to the phone and every column crushes; with it, the table keeps its proportions and
 *     the viewer swipes.
 *  3. **The screen SAYS there is more.** A scrollbar you only find by guessing is not
 *     communication. The fade + arrow appear when content is actually hidden and disappear when
 *     you reach the end, and the region is labelled for a screen reader.
 *
 *  What it does NOT do: decide columns, sorting or content. Each table keeps its own markup —
 *  this is a frame, not a data-table abstraction. Use `TH` for the header cell so the two header
 *  styles that drifted apart (38 places said one thing, 18 another) stay one thing.
 *
 *  ⚠ ANYTHING THAT POPS OUT OF A ROW MUST ESCAPE THIS FRAME — USE `Menu`, NOT A BARE ABSOLUTE
 *  PANEL. Both elements here establish a clipping context (`overflow-hidden` on the card for the
 *  corners, `overflow-x-auto` on the scroller), so a dropdown positioned `absolute` inside a cell
 *  is sliced off at the table's edge. That is not hypothetical: it happened on the Intake years
 *  round-state badge on 2026-09-08, and the owner reported it as *"clicking the close opens
 *  something, but it is hidden — there is a line below close but nothing is showing"* — the line
 *  being the top of the panel. It was fixed in the PRIMITIVE rather than by loosening the table:
 *  `Menu` renders its panel through a portal on `document.body`, the one placement no ancestor can
 *  clip. This frame put the same trap on fourteen tables instead of one, so the rule is worth
 *  stating here: pop-outs go through `Menu`.
 */
export const TH =
  'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-ground-600'

/** The same cell, right-aligned — for money and counts, which read better on their right edge. */
export const TH_RIGHT = `${TH.replace('text-left', 'text-right')}`

export default function TableFrame({
  children,
  minWidth = 640,
  label,
  bare = false,
  className = '',
}: {
  children: React.ReactNode
  /** The floor in px below which the table scrolls instead of squashing. Set it to the width the
   *  columns genuinely need — a floor that is too low re-creates the squash it exists to stop. */
  minWidth?: number
  /** Names the scrollable region for a screen reader (e.g. "Reviewers"). */
  label?: string
  /** For a table that already sits INSIDE a card (Course data's coverage panel): drop this
   *  component's own border, background and shadow, keep the scroll floor and the cue. A card
   *  inside a card reads as two objects and flattens the hierarchy. */
  bare?: boolean
  className?: string
}) {
  const { t } = useT()
  const scroller = useRef<HTMLDivElement>(null)
  const [more, setMore] = useState(false)

  // `more` is measured, never assumed: the cue must not claim there is content to the right when
  // the table already fits, and must appear the moment it does not (a rotated phone, a resized
  // window, a filter that widens a column).
  const measure = useCallback(() => {
    const el = scroller.current
    if (!el) return
    setMore(el.scrollWidth - el.clientWidth - el.scrollLeft > 4)
  }, [])

  useEffect(() => {
    measure()
    const el = scroller.current
    if (!el) return
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
    ro?.observe(el)
    window.addEventListener('resize', measure)
    return () => {
      ro?.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [measure, children])

  return (
    <div className={`relative ${className}`}>
      {/* The CARD clips — corners only. */}
      <div className={bare
        ? 'overflow-hidden'
        : 'overflow-hidden rounded-xl border border-ground-200 bg-ground-0 shadow-sm'}>
        {/* The SCROLLER is its own element. Never merge these two. */}
        <div
          ref={scroller}
          onScroll={measure}
          role="region"
          aria-label={label}
          tabIndex={0}
          data-testid="table-scroller"
          className="overflow-x-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-fill"
        >
          <div style={{ minWidth: `${minWidth}px` }}>{children}</div>
        </div>
      </div>

      {more && (
        <div
          aria-hidden
          data-testid="table-more-cue"
          className="pointer-events-none absolute inset-y-0 right-0 flex w-12 items-center
                     justify-end rounded-r-xl bg-gradient-to-r from-transparent to-ground-0 pr-2"
        >
          <span className="text-lg font-semibold text-brand-fill">›</span>
        </div>
      )}
      {/* Said in words as well as drawn — the cue is decoration to a screen reader. */}
      {more && (
        <p className="mt-1.5 text-xs text-ground-500 md:hidden" data-testid="table-more-note">
          {t('admin.table.scrollHint')}
        </p>
      )}
    </div>
  )
}
