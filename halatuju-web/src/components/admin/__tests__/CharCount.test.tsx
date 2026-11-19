/**
 * @jest-environment jsdom
 */
import { render, screen } from '@testing-library/react'

import { CharCount } from '../CharCount'

it('sits on its own line, right-aligned, and keeps the caller\'s tint and id', () => {
  render(<CharCount id="c" testId="c-t" className="text-critical-600">3 / 10</CharCount>)
  const el = screen.getByTestId('c-t')
  expect(el.tagName).toBe('P')
  expect(el.id).toBe('c')
  expect(el.className).toContain('text-right')
  expect(el.className).toContain('text-critical-600')
  expect(el.textContent).toBe('3 / 10')
})
