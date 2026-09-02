/**
 * @jest-environment jsdom
 *
 * The theme switch, as a person actually uses it (Layer 1 F7d).
 *
 * `theme.test.ts` is STRUCTURAL — it reads this file as text and asserts what it must and must not
 * contain. This one runs it. The two catch different things: a structural guard cannot tell you
 * that clicking "Dark" paints the page, and this cannot tell you the control is mounted on the
 * sponsor shell. Neither replaces the other.
 *
 * What is deliberately NOT tested here: what dark mode looks like. That is a browser question and
 * is reviewed on the sandbox in both modes — a passing test here says the machinery is right, never
 * that the result is good.
 */
import { render, screen, fireEvent } from '@testing-library/react'
import ThemeSelector from './ThemeSelector'
import { THEME_ATTR, THEME_STORAGE_KEY } from '@/lib/theme'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ locale: 'en', t: (k: string) => k }) }))

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute(THEME_ATTR)
})

describe('ThemeSelector', () => {
  it('offers light, dark and auto', () => {
    render(<ThemeSelector />)
    const options = screen.getAllByRole('option').map((o) => (o as HTMLOptionElement).value)
    expect(options).toEqual(['light', 'dark', 'auto'])
  })

  it('starts on auto when the device has never been told otherwise', () => {
    render(<ThemeSelector />)
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('auto')
  })

  it('shows the mode this device already stored', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    render(<ThemeSelector />)
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('dark')
  })

  it('paints and remembers the mode a person picks', () => {
    render(<ThemeSelector />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'dark' } })

    expect(document.documentElement.getAttribute(THEME_ATTR)).toBe('dark')
    // The storage key is the HOME of this choice, not a cache of an account value — owner ruling,
    // 2026-09-02. If an account write path is ever added, this assertion still has to hold.
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('ignores rubbish in storage rather than painting it', () => {
    // Anyone can type into localStorage, and `data-theme` goes straight onto <html>.
    window.localStorage.setItem(THEME_STORAGE_KEY, 'midnight')
    render(<ThemeSelector />)
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('auto')
  })

  it('survives storage throwing, which private-mode Safari does on READ', () => {
    const getItem = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    // A theme is never worth an exception on a page a person is trying to use.
    expect(() => render(<ThemeSelector />)).not.toThrow()
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('auto')
    getItem.mockRestore()
  })
})
