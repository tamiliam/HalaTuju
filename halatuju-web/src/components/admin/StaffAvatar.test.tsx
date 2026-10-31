/**
 * @jest-environment jsdom
 *
 * A staff member's photo, or their initials (common profile S2). A signed URL that has expired falls
 * back to the initials rather than a broken image.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import StaffAvatar, { initialsOf } from './StaffAvatar'

it('draws the photo when there is one', () => {
  render(<StaffAvatar name="Priya Devi" photoUrl="https://signed/p.webp" size={40} />)
  const img = screen.getByTestId('staff-avatar-photo') as HTMLImageElement
  expect(img.src).toBe('https://signed/p.webp')
  expect(img.style.width).toBe('40px')
})

it('falls back to the initials when the photo cannot load (an expired link)', () => {
  render(<StaffAvatar name="Priya Devi" photoUrl="https://signed/old.webp" />)
  fireEvent.error(screen.getByTestId('staff-avatar-photo'))
  expect(screen.getByTestId('staff-avatar-initials').textContent).toBe('PD')
})

it('initials: two letters, upper case, never empty', () => {
  expect(initialsOf('kavitha raman devi')).toBe('KR')
  expect(initialsOf('  ')).toBe('?')
  expect(initialsOf(undefined)).toBe('?')
})
