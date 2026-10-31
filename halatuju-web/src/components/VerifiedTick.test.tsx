/**
 * @jest-environment jsdom
 *
 * VerifiedTick on a phone (Mobile M1a). Its explanation ("Matches MyKad") was a `title` only, which
 * a phone never shows. A tap now opens it — and the sequence an iPhone sends for a tap (a touch
 * pointer, a compatibility mouseover, then the click) must leave it OPEN.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import VerifiedTick from './VerifiedTick'

const LABEL = 'Matches MyKad'

describe('VerifiedTick', () => {
  it('a tap shows the label, and it stays shown', () => {
    render(<VerifiedTick label={LABEL} />)
    const tick = screen.getByRole('button', { name: LABEL })
    fireEvent.mouseOver(tick)
    fireEvent.click(tick)
    expect(screen.getByRole('tooltip').textContent).toBe(LABEL)
  })

  it('a second tap, a tap elsewhere, or Escape hides it', () => {
    render(<div><VerifiedTick label={LABEL} /><p>elsewhere</p></div>)
    const tick = screen.getByRole('button', { name: LABEL })
    fireEvent.click(tick)
    fireEvent.click(tick)
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.click(tick)
    fireEvent.pointerDown(screen.getByText('elsewhere'))
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.click(tick)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('keeps the seal an image named by its label, with the desktop title', () => {
    render(<VerifiedTick label={LABEL} />)
    const img = screen.getByRole('img', { name: LABEL })
    expect(img.getAttribute('title')).toBe(LABEL)
  })
})
