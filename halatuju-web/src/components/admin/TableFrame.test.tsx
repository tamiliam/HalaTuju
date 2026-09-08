/**
 * @jest-environment jsdom
 *
 * TableFrame — the promise it keeps for a phone (owner, 2026-09-08).
 *
 * The rules under test are the three the owner asked for, in his words: a table never clips, it
 * keeps its shape rather than squashing, and the screen SAYS when there is more to the right.
 * jsdom reports every element as 0×0, so the cue's measurement is driven directly here — that is
 * the only part a unit test can reach, and it is the part that was missing everywhere.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import TableFrame, { TH, TH_RIGHT } from './TableFrame'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k }),
}))

/** Pretend the scroller has more content than fits (jsdom has no layout). */
function widen(el: HTMLElement, { scrollWidth = 900, clientWidth = 400, scrollLeft = 0 } = {}) {
  Object.defineProperty(el, 'scrollWidth', { value: scrollWidth, configurable: true })
  Object.defineProperty(el, 'clientWidth', { value: clientWidth, configurable: true })
  Object.defineProperty(el, 'scrollLeft', { value: scrollLeft, configurable: true, writable: true })
}

const table = () => (
  <table><tbody><tr><td>Kavi</td></tr></tbody></table>
)

describe('a table never clips', () => {
  it('clips its CORNERS on the card and scrolls on a separate element', () => {
    // ⚠ The one mistake that cut Intake years off was putting both on one div: a card with
    // `overflow-hidden` and no inner scroller eats the columns that do not fit.
    const { container } = render(<TableFrame>{table()}</TableFrame>)
    const card = container.querySelector('.overflow-hidden') as HTMLElement
    const scroller = screen.getByTestId('table-scroller')
    expect(card).toBeTruthy()
    expect(scroller.className).toContain('overflow-x-auto')
    expect(card.contains(scroller)).toBe(true)
    expect(card).not.toBe(scroller)
  })

  it('bare drops the card but never the scroller', () => {
    render(<TableFrame bare>{table()}</TableFrame>)
    const scroller = screen.getByTestId('table-scroller')
    expect(scroller.className).toContain('overflow-x-auto')
    expect(scroller.parentElement?.className).not.toContain('border')
  })
})

describe('columns keep their shape', () => {
  it('holds a floor, so a narrow screen scrolls instead of crushing the columns', () => {
    render(<TableFrame minWidth={820}>{table()}</TableFrame>)
    const inner = screen.getByTestId('table-scroller').firstElementChild as HTMLElement
    expect(inner.style.minWidth).toBe('820px')
  })
})

describe('the screen says there is more', () => {
  it('shows the cue and the words only while content is actually hidden', async () => {
    render(<TableFrame label="Reviewers">{table()}</TableFrame>)
    const scroller = screen.getByTestId('table-scroller')

    // Fits: no claim of more.
    expect(screen.queryByTestId('table-more-cue')).toBeNull()
    expect(screen.queryByTestId('table-more-note')).toBeNull()

    // Wider than the viewport: cue AND a sentence, because a fade is invisible to a screen reader.
    widen(scroller)
    fireEvent.scroll(scroller)
    await waitFor(() => expect(screen.getByTestId('table-more-cue')).toBeTruthy())
    expect(screen.getByTestId('table-more-note').textContent).toBe('admin.table.scrollHint')

    // Scrolled to the end: the claim goes away rather than lying about more.
    widen(scroller, { scrollWidth: 900, clientWidth: 400, scrollLeft: 500 })
    fireEvent.scroll(scroller)
    await waitFor(() => expect(screen.queryByTestId('table-more-cue')).toBeNull())
  })

  it('names the scrolling region and lets a keyboard reach it', () => {
    render(<TableFrame label="Reviewers">{table()}</TableFrame>)
    const scroller = screen.getByRole('region', { name: 'Reviewers' })
    // A region nobody can focus cannot be scrolled without a mouse.
    expect(scroller.getAttribute('tabindex')).toBe('0')
  })
})

describe('one header style', () => {
  it('is small-caps and aligned, with a right variant for figures', () => {
    // 38 places said one thing and 18 said another before this constant existed.
    expect(TH).toContain('uppercase')
    expect(TH).toContain('text-left')
    expect(TH_RIGHT).toContain('text-right')
    expect(TH_RIGHT).not.toContain('text-left')
  })
})
