/**
 * @jest-environment jsdom
 *
 * Mobile M4b: the logo is a plain <img> (next/image was ~4.5 kB of JavaScript on every student route
 * for this one picture) that still asks Next's optimiser for the SAME addresses next/image wrote:
 * 1x and 2x, each rounded up to Next's next default size, quality 75. A remote tenant logo is used
 * as it is (it was `unoptimized`).
 */
import { render, screen } from '@testing-library/react'
import BrandLogo, { optimised } from './BrandLogo'

let mockLogo = '/logo-icon.png'
jest.mock('@/lib/branding-context', () => ({ useBranding: () => ({ logoUrl: mockLogo, logoAlt: 'HalaTuju' }) }))

it('asks the optimiser for 1x and 2x at Next\'s own sizes (120 px → 128 and 256)', () => {
  mockLogo = '/logo-icon.png'
  render(<BrandLogo width={120} height={40} priority />)
  const img = screen.getByAltText('HalaTuju')
  expect(img.getAttribute('src')).toBe('/_next/image?url=%2Flogo-icon.png&w=256&q=75')
  expect(img.getAttribute('srcset')).toBe(
    '/_next/image?url=%2Flogo-icon.png&w=128&q=75 1x, /_next/image?url=%2Flogo-icon.png&w=256&q=75 2x')
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

it('rounds each width UP to a size the optimiser serves', () => {
  expect(optimised('/a.png', 90)).toContain('&w=96&')
  expect(optimised('/a.png', 100)).toContain('&w=128&')
  expect(optimised('/a.png', 200)).toContain('&w=256&')
  expect(optimised('/a.png', 5000)).toContain('&w=3840&')
})

it('uses a remote tenant logo as it is, with no optimiser and no srcset', () => {
  mockLogo = 'https://cdn.example.org/logo.png'
  render(<BrandLogo width={90} height={48} />)
  const img = screen.getByAltText('HalaTuju')
  expect(img.getAttribute('src')).toBe('https://cdn.example.org/logo.png')
  expect(img.getAttribute('srcset')).toBeNull()
  expect(img.getAttribute('loading')).toBe('lazy')
})
