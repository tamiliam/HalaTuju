/**
 * @jest-environment jsdom
 *
 * InfoTip on a phone (Mobile M1a). The defect: an iPhone tap fires `mouseenter` and then `click`;
 * the old component opened on the first and TOGGLED shut on the second, so the help never showed.
 * These tests dispatch the same sequence a tap produces — a touch pointer entering, then a click —
 * and check the bubble is still there. A source-shape test could not see this: it is the ORDER of
 * two events that broke it. The bubble is a lazily loaded chunk, so an opening is awaited
 * (`findByRole`); a closing is synchronous.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import InfoTip from './InfoTip'

const TEXT = 'Your household income is the total of everyone living with you.'
const trigger = () => screen.getByRole('button', { name: TEXT })

/** jsdom has no PointerEvent with `pointerType`, so the property is put on the event by hand. */
function pointer(el: Element, type: 'pointerover' | 'pointerout' | 'pointerdown', pointerType: string) {
  const e = new MouseEvent(type, { bubbles: true, cancelable: true })
  Object.defineProperty(e, 'pointerType', { value: pointerType })
  act(() => { el.dispatchEvent(e) })
}

describe('InfoTip', () => {
  it('a TAP opens it and it stays open (touch enter, then click)', async () => {
    render(<InfoTip text={TEXT} />)
    // What iOS Safari actually sends for one tap: the pointer arrives (touch), a COMPATIBILITY
    // mouseover follows, then the click. The old component opened on the mouse event and the click
    // toggled it straight back shut.
    pointer(trigger(), 'pointerover', 'touch')
    fireEvent.mouseOver(trigger())
    fireEvent.click(trigger())
    expect((await screen.findByRole('tooltip')).textContent).toContain(TEXT)
  })

  it('a second tap on the i closes it', () => {
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    fireEvent.click(trigger())
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('a tap anywhere else closes it', async () => {
    render(<div><InfoTip text={TEXT} /><p>elsewhere</p></div>)
    fireEvent.click(trigger())
    await screen.findByRole('tooltip')
    pointer(screen.getByText('elsewhere'), 'pointerdown', 'touch')
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('Escape closes it', async () => {
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    await screen.findByRole('tooltip')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('a real MOUSE still opens it on hover and closes it on leave', async () => {
    render(<InfoTip text={TEXT} />)
    pointer(trigger(), 'pointerover', 'mouse')
    expect(await screen.findByRole('tooltip')).toBeTruthy()
    pointer(trigger(), 'pointerout', 'mouse')
    // a short grace, so the pointer can cross onto the bubble
    await act(async () => { await new Promise((r) => setTimeout(r, 300)) })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('a touch "enter" alone never opens it — a finger is not a hover', () => {
    render(<InfoTip text={TEXT} />)
    pointer(trigger(), 'pointerover', 'touch')
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('keyboard: Enter on the focused i opens it; moving focus on closes it', async () => {
    render(<div><InfoTip text={TEXT} /><button type="button">next</button></div>)
    trigger().focus()
    fireEvent.click(trigger())
    expect(await screen.findByRole('tooltip')).toBeTruthy()
    fireEvent.blur(trigger(), { relatedTarget: screen.getByRole('button', { name: 'next' }) })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('a tap on the bubble itself keeps it open (Chrome blurs the focused i to <body>)', async () => {
    render(<InfoTip text={TEXT} />)
    trigger().focus()
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    // Chrome's tap on plain text: focus leaves the button for nothing (relatedTarget null).
    fireEvent.blur(trigger(), { relatedTarget: null })
    expect(screen.queryByRole('tooltip')).toBe(bubble)
  })

  it('a tap on the bubble itself does not count as a tap elsewhere (it is a portal now)', async () => {
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    pointer(bubble, 'pointerdown', 'touch')
    expect(screen.queryByRole('tooltip')).toBe(bubble)
  })

  it('says whether it is open, for a screen reader', () => {
    render(<InfoTip text={TEXT} />)
    expect(trigger().getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(trigger())
    expect(trigger().getAttribute('aria-expanded')).toBe('true')
  })
})

/**
 * The bubble is drawn on `document.body`, `position: fixed`, so a table frame (`overflow-hidden` /
 * `overflow-x-auto`) can no longer clip it (seen live: Team -> Reviewers, the greyed Delete's reason
 * at the right edge). jsdom does no layout, so the trigger's box and the bubble's width are given.
 */
describe('InfoTip — placed above the page, not inside its parent', () => {
  const WIDTH = 256
  let rect = { left: 0, right: 0, top: 0, bottom: 0, width: 0, height: 0 }
  let viewport = 0
  let clip = { left: 0, right: 400, top: 0, bottom: 800 }
  const restore: Array<() => void> = []

  function stub<T extends object>(target: T, key: string, get: () => unknown) {
    const before = Object.getOwnPropertyDescriptor(target, key)
    Object.defineProperty(target, key, { configurable: true, get })
    restore.push(() => {
      if (before) Object.defineProperty(target, key, before)
      else delete (target as Record<string, unknown>)[key]
    })
  }

  /** The `i` (its root span) sits at `left`..`left+18`, its top at `top`. */
  function at(left: number, top = 100) {
    rect = { left, right: left + 18, top, bottom: top + 18, width: 18, height: 18 }
  }

  beforeEach(() => {
    viewport = 400
    clip = { left: 0, right: 400, top: 0, bottom: 800 }
    at(100)
    stub(window, 'innerHeight', () => 800)
    stub(HTMLElement.prototype, 'offsetWidth', () => WIDTH)
    stub(HTMLElement.prototype, 'offsetHeight', () => 60)
    stub(document.documentElement, 'clientWidth', () => viewport)
    const real = Element.prototype.getBoundingClientRect
    Element.prototype.getBoundingClientRect = function (this: Element) {
      if (this.getAttribute('data-testid') === 'clip') return { ...clip, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) } as DOMRect
      return (this.contains(trigger()) ? { ...rect, x: rect.left, y: rect.top, toJSON: () => ({}) } : real.call(this)) as DOMRect
    }
    restore.push(() => { Element.prototype.getBoundingClientRect = real })
  })
  afterEach(() => { while (restore.length) restore.pop()!() })

  const caret = (b: HTMLElement) => b.firstElementChild as HTMLElement

  it('is rendered on document.body, outside a clipping table frame', async () => {
    render(
      <div className="overflow-hidden" data-testid="frame">
        <div className="overflow-x-auto"><InfoTip text={TEXT} /></div>
      </div>,
    )
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    expect(screen.getByTestId('frame').contains(bubble)).toBe(false)
    expect(bubble.parentElement).toBe(document.body)
    expect(bubble.className).toContain('fixed')
    expect(bubble.className).not.toContain('absolute')
  })

  it('sits under the i, centred on it, with the caret on the i', async () => {
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    // centre 109 - 128 = -19 -> slid to the 8 px margin; the caret moves to stay on the i.
    expect(bubble.style.left).toBe('8px')
    expect(bubble.style.top).toBe('128px')   // 18 px trigger bottom at 118, plus the 10 px gap
    expect(caret(bubble).style.left).toBe('101px')
    expect(bubble.style.visibility).toBe('')
  })

  it('stays 8 px inside the right edge, the caret still pointing at the i', async () => {
    at(370)   // the i's centre at 379 on a 400 px screen
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    expect(bubble.style.left).toBe(`${400 - 8 - WIDTH}px`)
    expect(caret(bubble).style.left).toBe(`${379 - (400 - 8 - WIDTH)}px`)
  })

  it('is centred when there is room either side', async () => {
    viewport = 1000
    at(491)   // centre 500
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    expect(bubble.style.left).toBe(`${500 - WIDTH / 2}px`)
    expect(caret(bubble).style.left).toBe(`${WIDTH / 2}px`)
  })

  it('follows its trigger when anything scrolls, and when the window resizes', async () => {
    viewport = 1000
    at(491)
    render(<div data-testid="scroller"><InfoTip text={TEXT} /></div>)
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    at(291, 40)
    // a scroll on an ANCESTOR (a table's own scroller) does not bubble: the listener captures it
    fireEvent.scroll(screen.getByTestId('scroller'))
    expect(bubble.style.left).toBe(`${300 - WIDTH / 2}px`)
    expect(bubble.style.top).toBe('68px')
    at(591, 200)
    act(() => { window.dispatchEvent(new Event('resize')) })
    expect(bubble.style.left).toBe(`${600 - WIDTH / 2}px`)
    expect(bubble.style.top).toBe('228px')
  })

  it('leaves nothing behind on document.body when it closes', async () => {
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    await screen.findByRole('tooltip')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(document.body.querySelector('[role="tooltip"]')).toBeNull()
  })

  it('flips ABOVE the i when there is no room below, the caret on the bubble\'s bottom edge', async () => {
    stub(window, 'innerHeight', () => 300)
    at(100, 270)   // trigger bottom 288: 288 + 10 + 60 overruns 300 - 8, and there is more room above
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    expect(bubble.style.top).toBe('200px')   // 270 - 10 - 60
    expect(caret(bubble).getAttribute('data-side')).toBe('bottom')
    expect(caret(bubble).style.left).toBe('101px')   // still on the i
  })

  it('stays below, caret on top, when it fits', async () => {
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    const bubble = await screen.findByRole('tooltip')
    expect(caret(bubble).getAttribute('data-side')).toBe('top')
  })

  it('closes when the i scrolls out of the screen', async () => {
    render(<InfoTip text={TEXT} />)
    fireEvent.click(trigger())
    await screen.findByRole('tooltip')
    at(100, 900)
    fireEvent.scroll(document.body)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('closes when the i scrolls out of its scrolling ancestor, and not while it is inside', async () => {
    render(<div data-testid="clip" style={{ overflow: 'auto' }}><InfoTip text={TEXT} /></div>)
    clip = { left: 0, right: 400, top: 0, bottom: 200 }
    fireEvent.click(trigger())
    await screen.findByRole('tooltip')
    fireEvent.scroll(screen.getByTestId('clip'))
    expect(screen.queryByRole('tooltip')).not.toBeNull()
    clip = { left: 0, right: 400, top: 300, bottom: 500 }   // the i (100-118) is now above the frame
    fireEvent.scroll(screen.getByTestId('clip'))
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('moving the mouse from the i onto the bubble keeps a hover-opened bubble open', async () => {
    render(<InfoTip text={TEXT} />)
    pointer(trigger(), 'pointerover', 'mouse')
    const bubble = await screen.findByRole('tooltip')
    pointer(trigger(), 'pointerout', 'mouse')
    pointer(bubble, 'pointerover', 'mouse')
    await act(async () => { await new Promise((r) => setTimeout(r, 300)) })
    expect(screen.queryByRole('tooltip')).not.toBeNull()
    pointer(bubble, 'pointerout', 'mouse')
    await act(async () => { await new Promise((r) => setTimeout(r, 300)) })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })
})
