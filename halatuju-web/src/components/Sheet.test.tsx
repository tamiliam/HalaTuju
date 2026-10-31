/**
 * @jest-environment jsdom
 *
 * The shared Sheet (Mobile M1b). What is tested is BEHAVIOUR a source guard cannot see: where focus
 * goes, what Tab and Escape do, what the backdrop does, that a non-dismissible sheet really cannot be
 * dismissed, and that the page underneath is held still (and freed again — including when two
 * sheets are stacked). Layout (bottom sheet vs dialog, keyboard lift) is measured in the browser.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import Sheet, { type SheetProps } from './Sheet'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

function Harness(props: Partial<SheetProps> & { onClose?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>opener</button>
      <Sheet open={open} title="Remove this course?" description="It leaves your saved list."
        {...props}
        onClose={() => { props.onClose?.(); setOpen(false) }}
        footer={props.footer ?? <button type="button">Remove</button>}>
        {props.children ?? <><input aria-label="first field" /><input aria-label="second field" /></>}
      </Sheet>
    </div>
  )
}

const openIt = () => {
  const opener = screen.getByRole('button', { name: 'opener' })
  opener.focus()
  fireEvent.click(opener)
  return opener
}

describe('Sheet', () => {
  it('renders nothing while closed', () => {
    render(<Harness />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('is a modal dialog, named by its title and described by its description', () => {
    render(<Harness />)
    openIt()
    const dialog = screen.getByRole('dialog', { name: 'Remove this course?' })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(document.getElementById(dialog.getAttribute('aria-describedby') ?? '')?.textContent)
      .toBe('It leaves your saved list.')
  })

  it('moves focus to the first field on open, and back to the opener on close', () => {
    render(<Harness />)
    const opener = openIt()
    expect(document.activeElement).toBe(screen.getByLabelText('first field'))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('keeps Tab inside: from the last control to the first, and Shift+Tab back round', () => {
    render(<Harness />)
    openIt()
    const close = screen.getByRole('button', { name: 'common.dismiss' })
    const last = screen.getByRole('button', { name: 'Remove' })
    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(close)
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)
  })

  it('closes on Escape, the backdrop and the ×', () => {
    const onClose = jest.fn()
    render(<Harness onClose={onClose} />)
    openIt()
    fireEvent.keyDown(document, { key: 'Escape' })
    openIt()
    fireEvent.click(document.querySelector('[data-sheet-backdrop]') as Element)
    openIt()
    fireEvent.click(screen.getByRole('button', { name: 'common.dismiss' }))
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('dismissible={false}: no ×, and neither Escape nor the backdrop closes it', () => {
    const onClose = jest.fn()
    render(<Harness onClose={onClose} dismissible={false} />)
    openIt()
    expect(screen.queryByRole('button', { name: 'common.dismiss' })).toBeNull()
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(document.querySelector('[data-sheet-backdrop]') as Element)
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('busy: nothing closes it while an action is in flight', () => {
    const onClose = jest.fn()
    render(<Harness onClose={onClose} busy />)
    openIt()
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(document.querySelector('[data-sheet-backdrop]') as Element)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('holds the page still while open and frees it on close', () => {
    document.body.style.overflow = 'auto'
    render(<Harness />)
    openIt()
    expect(document.body.style.overflow).toBe('hidden')
    expect(document.documentElement.style.overflow).toBe('hidden')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(document.body.style.overflow).toBe('auto')
  })

  it('two sheets: Escape closes only the top one, and the page stays held until both are shut', () => {
    function Two() {
      const [a, setA] = useState(true)
      const [b, setB] = useState(true)
      return (<>
        <Sheet open={a} onClose={() => setA(false)} title="Under"><p>under</p></Sheet>
        <Sheet open={b} onClose={() => setB(false)} title="Over"><p>over</p></Sheet>
      </>)
    }
    document.body.style.overflow = ''
    render(<Two />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Over' })).toBeNull()
    expect(screen.getByRole('dialog', { name: 'Under' })).toBeTruthy()
    expect(document.body.style.overflow).toBe('hidden')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.body.style.overflow).toBe('')
  })

  it('onSubmit makes body and footer one form: the footer submit button submits', () => {
    const onSubmit = jest.fn((e: { preventDefault: () => void }) => e.preventDefault())
    render(<Harness onSubmit={onSubmit} footer={<button type="submit">Save</button>} />)
    openIt()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })
})
