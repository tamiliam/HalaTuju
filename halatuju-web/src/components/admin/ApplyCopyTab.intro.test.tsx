/**
 * @jest-environment jsdom
 *
 * Request #34 (2026-10-19): an opening paragraph's line breaks were lost on display. The admin's
 * "standard wording" preview renders the intro as text with `whitespace-pre-line`, the same rule
 * as the student apply page (`page.gift.test.tsx` D5) — never as HTML.
 */
import { render, screen } from '@testing-library/react'

import { StandardWording } from './ApplyCopyTab'

const mockIntro = 'First paragraph.\n\nSecond paragraph.'

jest.mock('@/lib/applyCopyPlatform', () => ({
  platformApplyCard: () => ({ title: 'Standard title', intro: mockIntro, criteria: ['One rule'] }),
}))

it('a two-paragraph intro keeps its blank line, shown as text', async () => {
  render(<StandardWording locale="en" t={(k: string) => k} />)
  const shown = await screen.findByTestId('standard-intro')
  expect(shown.textContent).toBe(mockIntro)
  expect(shown.className).toContain('whitespace-pre-line')
  expect(shown.querySelector('br')).toBeNull()
})
