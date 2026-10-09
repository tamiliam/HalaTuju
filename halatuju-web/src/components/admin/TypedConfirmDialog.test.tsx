/**
 * @jest-environment jsdom
 *
 * The typed confirmation (staff delete, 2026-10-09): nothing happens until the exact phrase is
 * typed. Compared trimmed, whitespace-collapsed and case-insensitive — the gift dialog's rule.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import TypedConfirmDialog from './TypedConfirmDialog'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const draw = (onConfirm = jest.fn()) => {
  render(<TypedConfirmDialog title="Delete Asha?" body="Their sign-in is removed."
    phrase="asha@example.org" cta="Delete" onCancel={jest.fn()} onConfirm={onConfirm} />)
  return onConfirm
}
const go = () => screen.getByTestId('typed-confirm-go') as HTMLButtonElement
const type = (v: string) => fireEvent.change(screen.getByRole('textbox'), { target: { value: v } })

it('starts disabled, and stays so for a near miss', () => {
  draw()
  expect(go().disabled).toBe(true)
  type('asha@example.or')
  expect(go().disabled).toBe(true)
})

it('opens on the exact phrase, forgiving case and stray spaces', () => {
  const onConfirm = draw()
  type('  ASHA@example.org ')
  expect(go().disabled).toBe(false)
  fireEvent.click(go())
  expect(onConfirm).toHaveBeenCalledTimes(1)
})

it('never fires from a click while disabled', () => {
  const onConfirm = draw()
  fireEvent.click(go())
  expect(onConfirm).not.toHaveBeenCalled()
})

it('names the consequence and the phrase to type', () => {
  draw()
  expect(screen.getByText('Their sign-in is removed.')).toBeTruthy()
  expect(screen.getByText('admin.programmes.deleteConfirmLabel')).toBeTruthy()
})
