/** @jest-environment jsdom */
import { render, screen } from '@testing-library/react'
import LazyApplyNotice from './LazyApplyNotice'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}))

describe('LazyApplyNotice', () => {
  it('draws the closed card once its chunk arrives', async () => {
    render(<LazyApplyNotice kind="closed" />)
    expect(await screen.findByTestId('apply-gift-closed')).toBeTruthy()
  })

  it('draws the already-applied card, with the opt-in button only when given', async () => {
    const { rerender } = render(<LazyApplyNotice kind="applied" />)
    expect(await screen.findByTestId('apply-already-applied')).toBeTruthy()
    expect(screen.queryByTestId('apply-already-others')).toBeNull()
    rerender(<LazyApplyNotice kind="applied" onSeeOpen={() => {}} />)
    expect(screen.getByTestId('apply-already-others')).toBeTruthy()
  })
})
