/**
 * @jest-environment jsdom
 *
 * Mobile M4b: the logo is a plain <img> (next/image was ~4.5 kB of JavaScript on every student route
 * for this one picture). Since the security patch the image optimiser is off, so every logo is used as it is.
 */
import { render, screen } from '@testing-library/react'
import BrandLogo from './BrandLogo'

let mockLogo = '/logo-icon.png'
jest.mock('@/lib/branding-context', () => ({ useBranding: () => ({ logoUrl: mockLogo, logoAlt: 'HalaTuju' }) }))

it('serves the logo as it is, with no optimiser address and no srcset', () => {
  mockLogo = '/logo-icon.png'
  render(<BrandLogo width={120} height={40} priority />)
  const img = screen.getByAltText('HalaTuju')
  expect(img.getAttribute('src')).toBe('/logo-icon.png')
  expect(img.getAttribute('srcset')).toBeNull()
  expect(img.getAttribute('width')).toBe('120')
  expect(img.getAttribute('loading')).toBe('eager')
  expect(img.getAttribute('fetchpriority')).toBe('high')
})

it.each([
  ['data:image/png;base64,AAAA'], ['blob:https://halatuju.xyz/1234'], ['/logos/tenant.svg'], ['/logos/tenant.SVG?v=2'],
])('passes %s through as it is, as next/image did (no optimiser, no srcset)', (src) => {
  mockLogo = src
  render(<BrandLogo width={120} height={40} />)
  const img = screen.getByAltText('HalaTuju')
  expect(img.getAttribute('src')).toBe(src)
  expect(img.getAttribute('srcset')).toBeNull()
  expect(img.getAttribute('fetchpriority')).toBeNull()
})

it('uses a remote tenant logo as it is, with no optimiser and no srcset', () => {
  mockLogo = 'https://cdn.example.org/logo.png'
  render(<BrandLogo width={90} height={48} />)
  const img = screen.getByAltText('HalaTuju')
  expect(img.getAttribute('src')).toBe('https://cdn.example.org/logo.png')
  expect(img.getAttribute('srcset')).toBeNull()
  expect(img.getAttribute('loading')).toBe('lazy')
})
