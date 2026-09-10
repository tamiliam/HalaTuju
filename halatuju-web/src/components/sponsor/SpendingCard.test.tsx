/**
 * @jest-environment jsdom
 *
 * The sponsor's spending card (S5).
 *
 * ⚠ The anonymity promise is kept on the SERVER (`spend_sponsor.py`, and the planted-identifier
 * tests in `test_spend_sponsor.py` / `test_sponsor_pool.py`). What these tests protect is the half
 * the server cannot: that the card renders every category the server sent — including the two that
 * must never be folded away — and that the arithmetic on screen cannot go wrong when `spent`
 * exceeds `released`.
 */
import { render, screen } from '@testing-library/react'
import SpendingCard from './SpendingCard'
import type { SponsorSpending } from '@/lib/api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, vars?: Record<string, string>) =>
      (vars ? `${k}:${Object.values(vars).join(',')}` : k),
    locale: 'en',
  }),
}))

const CARD: SponsorSpending = {
  promised: '2000.00',
  released: '1400.00',
  spent: '1120.00',
  left: '280.00',
  as_at: '2026-09-10',
  categories: [
    { code: 'food', label: 'Food & drink', total: '540.00' },
    { code: 'groceries', label: 'Groceries', total: '210.50' },
    { code: 'transport', label: 'Transport', total: '136.00' },
    { code: 'study', label: 'Books & study supplies', total: '98.70' },
    { code: 'phone', label: 'Phone & internet', total: '60.00' },
    { code: 'health', label: 'Health & pharmacy', total: '39.45' },
    { code: 'other', label: '', total: '35.35' },
  ],
}

const withCategories = (categories: SponsorSpending['categories']) =>
  ({ ...CARD, categories })

describe('the four numbers', () => {
  it('shows all four, formatted from the STRING the server sent', () => {
    render(<SpendingCard spending={CARD} />)
    const figures = screen.getByTestId('spending-figures')
    expect(figures.textContent).toContain('RM2,000.00')
    expect(figures.textContent).toContain('RM1,400.00')
    expect(figures.textContent).toContain('RM1,120.00')
    expect(figures.textContent).toContain('RM280.00')
  })

  it('draws the bar as released against promised', () => {
    render(<SpendingCard spending={CARD} />)
    expect(screen.getByTestId('released-bar').style.width).toBe('70%')
  })

  it('never lets the bar overflow when spending exceeds what we released', () => {
    // ⚠ NOT A BUG: the wallet is the student's own and a parent may top it up. The bar must not
    // spill out of its track, and nothing here may imply the student overspent our money.
    render(<SpendingCard spending={{
      ...CARD, promised: '500.00', released: '900.00', spent: '900.00', left: '0.00',
    }} />)
    expect(screen.getByTestId('released-bar').style.width).toBe('100%')
  })

  it('survives a student with nothing promised without dividing by zero', () => {
    render(<SpendingCard spending={{ ...CARD, promised: '0.00', released: '0.00' }} />)
    expect(screen.getByTestId('released-bar').style.width).toBe('0%')
  })
})

describe('the ranked list', () => {
  it('draws one row per category, with the money', () => {
    render(<SpendingCard spending={CARD} />)
    const list = screen.getByTestId('spending-list')
    expect(list.querySelectorAll('li')).toHaveLength(7)
    expect(list.textContent).toContain('RM540.00')
    expect(list.textContent).toContain('RM35.35')
  })

  it('shows "Sent to a person" as its own row, never folded away', () => {
    // ⚠ OWNER RULING. It is the one line a careful sponsor most needs to see.
    render(<SpendingCard spending={withCategories([
      ...CARD.categories.slice(0, 6),
      { code: 'transfer', label: 'Sent to a person', total: '0.50' },
    ])} />)
    expect(screen.getByTestId('spending-list').textContent)
      .toContain('sponsorPortal.myStudents.detail.spend.cat.transfer')
  })

  it('shows "Not yet sorted" as its own row, never folded away', () => {
    // ⚠ It is what stops the other nine reading as complete when they are not.
    render(<SpendingCard spending={withCategories([
      ...CARD.categories.slice(0, 6),
      { code: 'unsorted', label: 'Not yet sorted', total: '0.25' },
    ])} />)
    expect(screen.getByTestId('spending-list').textContent)
      .toContain('sponsorPortal.myStudents.detail.spend.cat.unsorted')
  })

  it('labels every row from i18n, never from the server label', () => {
    // ⚠ The server sends an English label for the officer's convenience; a sponsor reading Tamil
    // must not be shown it. The card resolves its own key per code.
    render(<SpendingCard spending={CARD} />)
    expect(screen.getByTestId('spending-list').textContent).not.toContain('Food & drink')
  })

  it('renders a list even when only one category has money', () => {
    render(<SpendingCard spending={withCategories(
      [{ code: 'food', label: 'Food & drink', total: '12.00' }])} />)
    expect(screen.getByTestId('spending-list').querySelectorAll('li')).toHaveLength(1)
  })
})

describe('the donut', () => {
  it('draws one arc per category, plus the track', () => {
    render(<SpendingCard spending={CARD} />)
    // 1 track + 7 slices
    expect(screen.getByTestId('spending-donut').querySelectorAll('circle')).toHaveLength(8)
  })

  it('is described for a screen reader rather than left as decoration', () => {
    render(<SpendingCard spending={CARD} />)
    expect(screen.getByTestId('spending-donut').getAttribute('aria-label'))
      .toBe('sponsorPortal.myStudents.detail.spend.chartLabel')
  })

  it('does not fall over when every total is zero', () => {
    render(<SpendingCard spending={withCategories(
      [{ code: 'food', label: 'Food & drink', total: '0.00' }])} />)
    expect(screen.getByTestId('spending-donut')).not.toBeNull()
  })
})

describe('the stamp and the note', () => {
  it('stamps the date the server gave it', () => {
    render(<SpendingCard spending={CARD} />)
    expect(document.body.textContent)
      .toContain('sponsorPortal.myStudents.detail.spend.asAt:2026-09-10')
  })

  it('carries the assumptions note', () => {
    render(<SpendingCard spending={CARD} />)
    expect(screen.getByText('sponsorPortal.myStudents.detail.spend.note')).not.toBeNull()
  })
})
