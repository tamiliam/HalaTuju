/**
 * @jest-environment jsdom
 *
 * Mobile M6b (owner, 2026-11-03): ON A PHONE a PDF opens in the phone's own viewer in a new tab — a 44 px Open,
 * never an iframe (iPhone draws page one only, without zoom). On a desktop the framed iframe it always was.
 * Images stay inline everywhere. "Phone" = narrow OR touch-first (`PHONE_QUERY`).
 */
import { render, screen } from '@testing-library/react'
import DocViewer, { PHONE_QUERY } from './DocViewer'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const PDF = { label: 'Slip', filename: 'slip.pdf', url: 'https://files.invalid/slip.pdf', kind: 'pdf' as const }
const IMG = { label: 'IC', filename: 'ic.jpg', url: 'https://files.invalid/ic.jpg', kind: 'image' as const }

function asDevice(phone: boolean) {
  window.matchMedia = jest.fn((q: string) => ({ matches: phone && q === PHONE_QUERY, media: q } as MediaQueryList))
}
afterEach(() => { delete (window as { matchMedia?: unknown }).matchMedia })

describe('the document viewer on a phone (Mobile M6b)', () => {
  it('a phone gets a 44 px Open link to the PDF in a new tab, and no iframe', () => {
    asDevice(true)
    render(<DocViewer doc={PDF} onClose={() => {}} />)
    expect(document.querySelector('iframe')).toBeNull()
    const open = screen.getByRole('link', { name: /admin\.scholarship\.docsDrawer\.viewer\.openPdf/ })
    expect(open.getAttribute('href')).toBe(PDF.url)
    expect(open.getAttribute('target')).toBe('_blank')
    expect(open.getAttribute('rel')).toContain('noreferrer')
    expect(open.className).toMatch(/\bmin-h-12\b/)
  })

  it('a desktop keeps the iframe, and no phone panel', () => {
    asDevice(false)
    render(<DocViewer doc={PDF} onClose={() => {}} />)
    expect(document.querySelector('iframe')?.getAttribute('src')).toBe(PDF.url)
    expect(document.querySelector('[data-pdf-phone]')).toBeNull()
  })

  it('a browser without matchMedia is treated as a desktop', () => {
    render(<DocViewer doc={PDF} onClose={() => {}} />)
    expect(document.querySelector('iframe')).not.toBeNull()
  })

  it('an image is inline on a phone too', () => {
    asDevice(true)
    render(<DocViewer doc={IMG} onClose={() => {}} />)
    expect(screen.getByRole('img', { name: 'IC' }).getAttribute('src')).toBe(IMG.url)
    expect(document.querySelector('[data-pdf-phone]')).toBeNull()
  })

  it('the phone test is "narrow OR touch-first"', () => {
    expect(PHONE_QUERY).toBe('(max-width: 767.98px), (pointer: coarse)')
  })
})
