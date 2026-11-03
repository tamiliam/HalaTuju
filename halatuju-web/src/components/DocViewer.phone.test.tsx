/**
 * @jest-environment jsdom
 *
 * Mobile M6b (owner, 2026-11-03): ON A PHONE a PDF opens in the phone's own viewer in a new tab — a 44 px Open,
 * never an iframe (iPhone draws page one only, without zoom). On a desktop the framed iframe it always was.
 * Images stay inline everywhere. "Phone" = below md BY WIDTH ONLY (`PHONE_QUERY`, M6b review): an iPad or a touch desktop
 * keeps the iframe, and so does every other caller of the viewer on a desktop.
 */
import { render, screen } from '@testing-library/react'
import DocViewer, { PHONE_QUERY } from './DocViewer'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const PDF = { label: 'Slip', filename: 'slip.pdf', url: 'https://files.invalid/slip.pdf', kind: 'pdf' as const }
const IMG = { label: 'IC', filename: 'ic.jpg', url: 'https://files.invalid/ic.jpg', kind: 'image' as const }

/** A device of `width` px, touch or not, answering media queries the way a browser does (each list item ORed). */
function device(width: number, touch: boolean) {
  const one = (q: string) => {
    const max = q.match(/max-width:\s*([\d.]+)px/)
    if (max) return width <= Number(max[1])
    if (/pointer:\s*coarse/.test(q)) return touch
    return false
  }
  window.matchMedia = jest.fn((q: string) => ({ matches: q.split(',').some((p) => one(p.trim())), media: q } as MediaQueryList))
}
const asDevice = (phone: boolean) => device(phone ? 390 : 1280, phone)
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
    // The shared viewer is unchanged from md for its other callers (ScholarContract, ScholarResults,
    // OrgRequestAttachments, SourceWitness): every class M6b added is `max-md:`, or restates the old size from md.
    const fromMd = (el: Element) => el.className.split(' ').filter((c) => c && !c.startsWith('max-md:'))
    const link = screen.getByRole('link', { name: /viewer\.newTab/ })
    expect(fromMd(link)).toEqual(['text-xs', 'text-primary-600', 'hover:underline'])
    expect(fromMd(screen.getByText('slip.pdf'))).toEqual(['truncate', 'text-xs', 'text-ground-400', 'md:text-[11px]'])
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

  it('an iPad or a touch desktop (wide, touch) keeps the iframe: the rule is width only', () => {
    device(1024, true)
    render(<DocViewer doc={PDF} onClose={() => {}} />)
    expect(document.querySelector('iframe')?.getAttribute('src')).toBe(PDF.url)
    expect(document.querySelector('[data-pdf-phone]')).toBeNull()
  })

  it('a phone in portrait (narrow, touch) and a narrow desktop window both get the Open link', () => {
    for (const touch of [true, false]) {
      device(360, touch)
      const { unmount } = render(<DocViewer doc={PDF} onClose={() => {}} />)
      expect(document.querySelector('iframe')).toBeNull()
      unmount()
    }
  })

  it('"phone" is below md by width only, the same line the payment controls hide at', () => {
    expect(PHONE_QUERY).toBe('(max-width: 767.98px)')
  })
})
