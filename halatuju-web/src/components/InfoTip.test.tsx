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
    fireEvent.blur(trigger())
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('says whether it is open, for a screen reader', () => {
    render(<InfoTip text={TEXT} />)
    expect(trigger().getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(trigger())
    expect(trigger().getAttribute('aria-expanded')).toBe('true')
  })
})
