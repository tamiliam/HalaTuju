/**
 * @jest-environment jsdom
 *
 * SelectWithOther re-syncs its mode on `value` ALONE (audit A3.15).
 *
 * The effect used to carry a lint suppression because it reads `options`; it now reads the options
 * through a ref. What must not change: a custom value arriving late flips the box to "Other", and
 * a CHANGED options list with the same value does NOT touch the mode.
 */
import { render, screen } from '@testing-library/react'
import SelectWithOther from './SelectWithOther'

const OPTS = [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }]
const view = (value: string, options = OPTS) => (
  <SelectWithOther value={value} onChange={() => {}} options={options} placeholder="pick" otherText="Other" />
)

describe('SelectWithOther', () => {
  it('flips to Other when a custom value arrives after mount', () => {
    const { rerender } = render(view(''))
    expect(screen.queryByRole('textbox')).toBeNull()
    rerender(view('custom text'))
    expect(screen.getByRole('textbox')).toBeTruthy()
  })

  it('a new options list with the same value does not change the mode', () => {
    const { rerender } = render(view('a'))
    expect(screen.queryByRole('textbox')).toBeNull()
    // "a" is no longer in the list, but the value did not change: the mode stays preset.
    rerender(view('a', [{ value: 'b', label: 'B' }]))
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('a known value stays preset', () => {
    render(view('b'))
    expect(screen.queryByRole('textbox')).toBeNull()
  })
})
