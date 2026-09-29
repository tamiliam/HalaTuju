/**
 * Static guard: the Home page's top bar fits a phone (TD-310, 2026-09-29).
 *
 * The failure it prevents. The bar (logo · Auto · English · Log in · Sign Up) was one row that
 * could not wrap. Measured in Chromium at 390 px wide it was 414 px in English, 432 in Malay and
 * 588 in Tamil, so the whole Home page scrolled sideways and "Log in" broke onto two lines — and
 * switching the product to Lexend (a wider face) made it worse. Now the controls drop under the
 * logo and wrap among themselves, and the login label never breaks.
 *
 * What this proves: the classes that do that are still there. What it does NOT prove: that the bar
 * fits — jsdom cannot lay out a page. That was measured in a real browser at 390 and 360 px in all
 * three languages (see CHANGELOG TD-310); this test keeps those classes from silently reverting.
 */
import { floorCount, readWeb } from '@/test/sourceGuard'

const home = readWeb('src/app/page.tsx', 'the Home page owns its own top bar (not AppHeader)')
const auth = readWeb('src/components/AuthButtons.tsx',
  'the Log in / Sign Up pair shared by the Home bar and the app header')

/** The className of the first element whose opening tag matches `tagRe`. */
function classOf(src: string, tagRe: RegExp): string {
  const m = src.match(new RegExp(`${tagRe.source}[^>]*?className="([^"]+)"`))
  if (!m) throw new Error(`no element matching ${tagRe} with a className — did the bar move?`)
  return m[1]
}

const classes = (s: string) => s.split(/\s+/)

describe('the Home top bar fits a phone', () => {
  it('the bar wraps, so the controls drop under the logo instead of widening the page', () => {
    expect(classes(classOf(home, /<nav/))).toEqual(expect.arrayContaining(['flex', 'flex-wrap']))
  })

  it('the logo never shrinks to make room', () => {
    // The first <div> inside the nav holds the logo.
    const logo = classOf(home, /<nav[^>]*>\s*<div/)
    expect(classes(logo)).toContain('shrink-0')
  })

  it('the controls wrap among themselves (Tamil labels are wider than a phone)', () => {
    const controls = home.match(/<\/div>\s*<div className="([^"]+)">\s*<ThemeSelector \/>/)
    expect(controls).not.toBeNull()
    expect(classes(controls![1])).toEqual(expect.arrayContaining(['flex', 'flex-wrap']))
  })

  it('"Log in" stays on one line, like "Sign Up" beside it', () => {
    const buttons = Array.from(auth.matchAll(/<button[\s\S]*?className="([^"]+)"/g), (m) => m[1])
    // The "Log in ▾" toggle, the Student item inside its menu, and "Sign Up".
    expect(buttons).toHaveLength(3)
    const [login, , signUp] = buttons
    expect(classes(login)).toContain('whitespace-nowrap')
    expect(classes(signUp)).toContain('whitespace-nowrap')
  })
})

// The TD-310 review found the same two defects elsewhere once Lexend (wider than the system font)
// was on: a label/value row that could not wrap, and a "Log in" label that broke. Measured at 360.
describe('other rows that must fit a 360 px phone (TD-310 review)', () => {
  it('the TVET requirement rows wrap, and neither half can force the card wider', () => {
    // Three TVET course pages reached 380–387 px at 360 before this.
    const card = readWeb('src/components/RequirementsCard.tsx',
      'the course page\'s requirements card; its TVET rows are a label/value pair')
    const rows = floorCount(
      Array.from(card.matchAll(/<div key=\{item\.key\} className="([^"]*justify-between[^"]*)">\s*<span className="([^"]+)">[\s\S]*?<span className="([^"]+)">/g)),
      2, 'TVET label/value rows', 'general and special requirements each draw one')
    for (const [, row, label, value] of rows) {
      expect(classes(row)).toContain('flex-wrap')
      expect(classes(label)).toContain('min-w-0')
      expect(classes(value)).toContain('min-w-0')
    }
  })

  it('"Log in" on /get-started stays on one line', () => {
    const page = readWeb('src/app/get-started/page.tsx', 'the sign-up chooser has its own Log in button')
    const btn = page.match(/className="([^"]+)"\s*>\s*\{t\('header\.login\.label'\)\}/)
    expect(btn).not.toBeNull()
    expect(classes(btn![1])).toContain('whitespace-nowrap')
  })
})
