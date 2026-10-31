/**
 * @jest-environment jsdom
 *
 * The course page's Save button on a phone (Mobile M1a). A tap sends a touch pointer AND a
 * compatibility mouseenter; the button listened to the mouse event, so saving a course flipped its
 * label to "Remove from saved" at once and left it there. Only a real mouse may count as a hover.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { CourseActions } from './CourseDetailShared'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('next/link', () => ({ __esModule: true, default: ({ children }: { children: unknown }) => children }))

function pointer(el: Element, type: 'pointerover' | 'pointerout', pointerType: string) {
  const e = new MouseEvent(type, { bubbles: true, cancelable: true })
  Object.defineProperty(e, 'pointerType', { value: pointerType })
  el.dispatchEvent(e)
}

const setup = () => {
  const onHoverStart = jest.fn()
  const onHoverEnd = jest.fn()
  render(<CourseActions isSaved isHovering={false} onSave={() => {}}
    onHoverStart={onHoverStart} onHoverEnd={onHoverEnd} />)
  return { button: screen.getByRole('button', { name: 'courseDetail.saved' }), onHoverStart, onHoverEnd }
}

describe('CourseActions save button', () => {
  it('a tap (touch pointer + compatibility mouse events) is never a hover', () => {
    const { button, onHoverStart } = setup()
    pointer(button, 'pointerover', 'touch')
    fireEvent.mouseOver(button)
    fireEvent.mouseEnter(button)
    fireEvent.click(button)
    expect(onHoverStart).not.toHaveBeenCalled()
  })

  it('a real mouse still hovers, and leaving ends it', () => {
    const { button, onHoverStart, onHoverEnd } = setup()
    pointer(button, 'pointerover', 'mouse')
    expect(onHoverStart).toHaveBeenCalledTimes(1)
    pointer(button, 'pointerout', 'mouse')
    expect(onHoverEnd).toHaveBeenCalledTimes(1)
  })
})
