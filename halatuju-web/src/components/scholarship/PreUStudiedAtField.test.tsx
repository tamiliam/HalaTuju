/**
 * @jest-environment jsdom
 *
 * Pre-U sprint: the "Pre-U institution" field. The route chips and the list open only while the
 * box has focus; the first chip follows their results; free text is offered as typed.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { readWeb } from '@/test/sourceGuard'
import PreUStudiedAtField from './PreUStudiedAtField'
import LazyPreUStudiedAtField from './LazyPreUStudiedAtField'

jest.mock('@/lib/i18n', () => ({
  ...jest.requireActual('@/lib/i18n'),
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p?.typed ? `${k}:${p.typed}` : k), locale: 'en' }),
}))
jest.mock('@/lib/preULists', () => ({
  ...jest.requireActual('@/lib/preULists'),
  loadPreULists: () => Promise.resolve({
    form6: [{ name: 'SMK SERI PUTERI', hint: 'Selangor' }],
    matric: [{ name: 'KOLEJ MATRIKULASI JOHOR', hint: 'Johor' }],
    university: [{ name: 'UNIVERSITI MALAYA', hint: 'PASUM' }],
    poly: [],
  }),
}))

async function draw(resultsHeld: string, variant: 'apply' | 'profile' = 'apply') {
  const onChange = jest.fn()
  render(<PreUStudiedAtField resultsHeld={resultsHeld} value="" onChange={onChange} variant={variant} />)
  await act(async () => { await Promise.resolve() })
  return onChange
}

describe('PreUStudiedAtField', () => {
  it('shows no chips and no list until the box has focus', async () => {
    await draw('stpm')
    expect(screen.queryByTestId('pre-u-chips')).toBeNull()
    expect(screen.queryByText('SMK SERI PUTERI')).toBeNull()
    fireEvent.focus(screen.getByRole('combobox'))
    expect(screen.getByTestId('pre-u-chips')).toBeTruthy()
  })

  it('hides the chips again when the box loses focus', async () => {
    await draw('stpm')
    const box = screen.getByRole('combobox')
    fireEvent.focus(box)
    fireEvent.blur(box)
    await act(async () => { await new Promise((r) => setTimeout(r, 200)) })
    expect(screen.queryByTestId('pre-u-chips')).toBeNull()
  })

  it('opens the chip that follows their results', async () => {
    await draw('matric')
    fireEvent.focus(screen.getByRole('combobox'))
    expect(screen.getByText('scholarship.preU.chip.matric').getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('scholarship.preU.chip.form6').getAttribute('aria-pressed')).toBe('false')
  })

  it('the first chip follows results that arrive after mount (review round 1)', async () => {
    const { rerender } = render(<PreUStudiedAtField resultsHeld={undefined} value="" onChange={jest.fn()} variant="apply" />)
    await act(async () => { await Promise.resolve() })
    rerender(<PreUStudiedAtField resultsHeld="diploma" value="" onChange={jest.fn()} variant="apply" />)
    fireEvent.focus(screen.getByRole('combobox'))
    expect(screen.getByText('scholarship.preU.chip.poly').getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('scholarship.preU.chip.form6').getAttribute('aria-pressed')).toBe('false')
  })

  it('uses the route tip on apply and the general tip on the profile', async () => {
    await draw('stpm', 'apply')
    expect(screen.getByText('scholarship.preU.tipApply.stpm')).toBeTruthy()
  })

  it('uses the general tip on the profile', async () => {
    await draw('diploma', 'profile')
    expect(screen.getByText('scholarship.preU.tipProfile')).toBeTruthy()
  })

  it('offers free text as typed', async () => {
    await draw('stpm')
    const box = screen.getByRole('combobox')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'SMK Tiada' } })
    expect(screen.getByText(/scholarship\.preU\.useAsTyped/)).toBeTruthy()
  })
})

describe('the lazy boundary (pays for /scholarship/apply first-load JS)', () => {
  it('draws nothing mid-flight, then the field', async () => {
    const { container } = render(
      <LazyPreUStudiedAtField resultsHeld="stpm" value="" onChange={() => {}} variant="apply" />)
    expect(container.innerHTML).toBe('')
    expect(await screen.findByRole('combobox')).toBeTruthy()
  })

  it('the apply page imports the lazy field, and the boundary owns a LITERAL import()', () => {
    const page = readWeb('src/app/scholarship/apply/page.tsx', 'the apply form')
    expect(page).toContain("from '@/components/scholarship/LazyPreUStudiedAtField'")
    expect(page).not.toMatch(/from\s+'@\/components\/scholarship\/PreUStudiedAtField'/)
    // the field's chips and lists stay out of the first-load modules (webpack keeps exports app-wide)
    expect(page).not.toMatch(/from\s+'@\/lib\/preULists'/)
    expect(readWeb('src/lib/preUStudiedAt.ts', 'the first-load rules')).not.toMatch(/import\(/)
    const lazy = readWeb('src/components/scholarship/LazyPreUStudiedAtField.tsx', 'the lazy boundary')
    expect(lazy).toMatch(/import\((\/\* webpackChunkName: '[a-z]{2}' \*\/ )?'@\/components\/scholarship\/PreUStudiedAtField'\)/)
    expect(lazy).not.toMatch(/webpack(Mode|Prefetch|Preload|Exports)/)
  })
})
