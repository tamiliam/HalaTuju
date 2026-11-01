/**
 * @jest-environment jsdom
 *
 * Mobile M3: the phone filter sheet. What a student can do in it — and what must NOT happen: focus
 * landing in a text field (a keyboard rising over the chips), a picked chip hidden behind "Show all",
 * the footer button doing anything but closing.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import SearchFilterSheet, { type FacetGroup } from './SearchFilterSheet'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k} ${Object.values(p).join(' ')}` : k) }),
}))

const STATES = ['Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan', 'Pahang', 'Perak', 'Selangor']

function setup(over: Partial<{ state: string; resultCount: number | null; canClear: boolean }> = {}) {
  const onQual = jest.fn()
  const onState = jest.fn()
  const onClose = jest.fn()
  const onClear = jest.fn()
  const groups: FacetGroup[] = [
    { key: 'qualification', title: 'Qualification', value: 'SPM', onChange: onQual,
      options: [{ value: 'SPM', label: 'SPM' }, { value: 'STPM', label: 'STPM' }] },
    { key: 'state', title: 'State', value: over.state ?? '', onChange: onState, collapseAfter: 6,
      options: STATES.map((s) => ({ value: s, label: s })) },
  ]
  render(<SearchFilterSheet open onClose={onClose} groups={groups}
    resultCount={over.resultCount === undefined ? 128 : over.resultCount}
    onClear={onClear} canClear={over.canClear ?? true} />)
  return { onQual, onState, onClose, onClear }
}

describe('SearchFilterSheet', () => {
  it('is a dialog named "Filters" that opens with focus on the FIRST CHIP, not a text field', () => {
    setup()
    expect(screen.getByRole('dialog', { name: 'discovery.filters' })).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'SPM' }))
    expect(document.querySelector('[role="dialog"] input')).toBeNull()
  })

  it('one tap picks a value; a tap on the picked chip clears that facet', () => {
    const { onQual } = setup()
    expect(screen.getByRole('button', { name: 'SPM' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: 'STPM' }).getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(screen.getByRole('button', { name: 'STPM' }))
    expect(onQual).toHaveBeenLastCalledWith('STPM')
    fireEvent.click(screen.getByRole('button', { name: 'SPM' }))
    expect(onQual).toHaveBeenLastCalledWith('')
  })

  it('a long facet shows its first six and "Show all (N)", which shows the rest', () => {
    setup()
    expect(screen.queryByRole('button', { name: 'Selangor' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'discovery.showAll 8' }))
    expect(screen.getByRole('button', { name: 'Selangor' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'discovery.showAll 8' })).toBeNull()
  })

  it('the PICKED chip is never hidden behind "Show all"', () => {
    setup({ state: 'Selangor' })
    const picked = screen.getByRole('button', { name: 'Selangor' })
    expect(picked.getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: 'discovery.showAll 8' })).toBeTruthy()
  })

  it('one result says "course", not "courses" (M3 review)', () => {
    setup({ resultCount: 1 })
    expect(screen.getByRole('button', { name: 'discovery.showCourse 1' })).toBeTruthy()
  })

  it('"Show N courses" only closes; Clear clears; Clear is off when nothing is picked', () => {
    const { onClose, onClear, onQual } = setup()
    fireEvent.click(screen.getByRole('button', { name: 'discovery.showCourses 128' }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onQual).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'search.clearFilters' }))
    expect(onClear).toHaveBeenCalledTimes(1)
  })

  it('Clear is disabled with nothing to clear, and the count reads "loading" mid-search', () => {
    setup({ canClear: false, resultCount: null })
    expect((screen.getByRole('button', { name: 'search.clearFilters' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('button', { name: 'common.loading' })).toBeTruthy()
  })

  it('every chip and button is a 44 px target (min-h-11 or taller)', () => {
    setup()
    for (const b of Array.from(document.querySelectorAll('[role="dialog"] button'))) {
      expect(b.className).toMatch(/\b(min-h-11|min-h-12|h-11)\b/)
    }
  })
})
