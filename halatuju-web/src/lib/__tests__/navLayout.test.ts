/**
 * Static guard: the student shell's rows fit a phone — the one student header (Mobile M2; Home's own
 * bar before it, TD-310), the onboarding header, and the grade rows.
 *
 * The failures it prevents.
 *   - TD-310 (2026-09-29): Home's bar was one row that could not wrap — 414 px in English, 432 in
 *     Malay and 588 in Tamil at 390 — so Home scrolled sideways. The fix let it wrap, and it then
 *     stood three rows (184 px) tall in every language. Mobile M2 replaced it with the ONE student
 *     header: a single row that cannot wrap because every item but the logo is a fixed, measured
 *     width — the logo, ONE action, the menu button. Two actions do not fit: "Log in" + "Sign up"
 *     measured 385 px in Tamil against 358 at 390 wide.
 *   - Mobile M2: in Malay the onboarding row (logo + "Langkah 2 daripada 3" + bars, 268 px wide)
 *     squeezed the logo to 74 px at 390 and 44 px at 360.
 *   - Mobile M2: the STPM row's "not counted" tag left the subject picker ~12 px on a phone.
 *
 * What this proves: the classes and the structure that do that are still there. What it does NOT
 * prove: that the rows fit — jsdom cannot lay out a page. mobile-check measures that in a real
 * browser (sandbox: header-*, onboarding-stepper, stpm-grade-rows) at 360 and 390 in all three
 * languages; this test keeps the structure from silently reverting.
 */
import { floorCount, readWeb } from '@/test/sourceGuard'

const home = readWeb('src/app/page.tsx', 'the Home page draws the shared student header')
const header = readWeb('src/components/AppHeader.tsx', 'the one student header (Mobile M2)')
const auth = readWeb('src/components/AuthButtons.tsx',
  'the desktop Log in ▾ / Sign Up pair in the student header')

/** The className of the first element whose opening tag matches `tagRe`. */
function classOf(src: string, tagRe: RegExp): string {
  const m = src.match(new RegExp(`${tagRe.source}[^>]*?className="([^"]+)"`))
  if (!m) throw new Error(`no element matching ${tagRe} with a className — did the bar move?`)
  return m[1]
}

const classes = (s: string) => s.split(/\s+/)

describe('one student header, one row on a phone (Mobile M2; was TD-310)', () => {
  it('Home draws the shared student header, not a bar of its own', () => {
    expect(home).toMatch(/<AppHeader \/>/)
    expect(home).not.toMatch(/<nav\b/)
    expect(home).not.toMatch(/<(ThemeSelector|LanguageSelector|AuthButtons)\b/)
  })

  it('the header row cannot wrap, and the logo never shrinks to make room', () => {
    const row = classOf(header, /<header[^>]*>\s*(?:\{\/\*[\s\S]*?\*\/\}\s*)?<div/)
    expect(classes(row)).toEqual(expect.arrayContaining(['flex', 'items-center']))
    expect(classes(row)).not.toContain('flex-wrap')
    expect(classes(classOf(header, /<Link href="\/"/))).toContain('shrink-0')
  })

  it('the phone side is ONE action and the menu button — never the two-button pair', () => {
    const start = header.indexOf('{/* Phone right side')
    expect(start).toBeGreaterThan(-1)
    const phone = header.slice(start, header.indexOf('</header>'))
    expect(classes(classOf(phone, /<div/))).toEqual(expect.arrayContaining(['shrink-0', 'lg:hidden']))
    expect(phone).not.toMatch(/<AuthButtons\b/)
    expect(phone).not.toMatch(/header\.signUp/)
    // Signed out, the one action is `logIn` (the student gate, or the sponsor login on /sponsor*).
    expect(phone).toMatch(/\) : logIn\}/)
    // "Log in" never breaks onto two lines, and both controls are 44 px targets.
    const login = header.match(/const LOG_IN = '([^']+)'/)
    expect(login).not.toBeNull()
    expect(classes(login![1])).toEqual(expect.arrayContaining(['whitespace-nowrap', 'min-h-11']))
    expect((header.match(/className=\{LOG_IN\}>\{t\('header\.login\.label'\)\}/g) ?? []).length).toBe(2)
    const menu = phone.match(/aria-label=\{t\('common\.menu'\)\}[\s\S]*?className="([^"]+)"/)
    expect(menu).not.toBeNull()
    expect(classes(menu![1])).toEqual(expect.arrayContaining(['h-11', 'w-11']))
  })

  it('before the desktop row arrives its 44 px height is already reserved (no 4 px jump)', () => {
    const slot = header.match(/<div className="([^"]*lg:flex[^"]*)"\s*onPointerEnter=\{fallback/)
    expect(slot).not.toBeNull()
    expect(classes(slot![1])).toEqual(expect.arrayContaining(['min-h-11', 'hidden', 'lg:flex']))
  })

  it('the bar never imports the menus\' heavy parts — they load on the first open', () => {
    // ⚠ The bundle budget is the real guard; this names the cause when it trips.
    // (`import type` is erased at build, so the menus' TYPES may be named.)
    expect(header).not.toMatch(/^import (?!type ).*(ThemeSelector|LanguageSelector|Sheet|AuthButtons|StudentMenus)['"]/m)
    expect(header).toMatch(/import\('\.\/StudentMenus'\)/)
  })

  it('"Log in" stays on one line in the desktop pair, like "Sign Up" beside it', () => {
    const buttons = Array.from(auth.matchAll(/<button[\s\S]*?className="([^"]+)"/g), (m) => m[1])
    // The "Log in ▾" toggle, the Student item inside its menu, and "Sign Up".
    expect(buttons).toHaveLength(3)
    const [login, , signUp] = buttons
    expect(classes(login)).toContain('whitespace-nowrap')
    expect(classes(signUp)).toContain('whitespace-nowrap')
  })
})

describe('the onboarding header fits a 360 px phone in Malay (Mobile M2)', () => {
  const flow = readWeb('src/components/FlowHeader.tsx', 'the onboarding header')
  const stepper = readWeb('src/components/ProgressStepper.tsx', 'the step indicator')
  const PAGES = [
    ['exam-type', 1], ['grades', 2], ['higher-grades', 2], ['stpm-grades', 2], ['profile', 3],
  ] as const

  it('the logo never shrinks', () => {
    expect(classes(classOf(flow, /<Link href="\/"/))).toContain('shrink-0')
  })

  it('the step words sit OVER the bars, so the indicator is only as wide as its words', () => {
    expect(classes(classOf(stepper, /return \(\s*<div/))).toEqual(expect.arrayContaining(['flex', 'flex-col']))
  })

  it('every onboarding page uses it, and none keeps a copy of its own', () => {
    for (const [page, step] of PAGES) {
      const src = readWeb(`src/app/onboarding/${page}/page.tsx`, 'an onboarding step')
      expect({ page, uses: src.includes(`<FlowHeader step={${step}} />`) }).toEqual({ page, uses: true })
      expect({ page, copy: /<ProgressStepper\b|<BrandLogo\b/.test(src) }).toEqual({ page, copy: false })
    }
  })
})

describe('the grade rows fit a phone (Mobile M2)', () => {
  it('an STPM row restacks below sm: the tag can never crush the subject', () => {
    const row = readWeb('src/components/StpmSubjectRow.tsx', 'one STPM subject row')
    const root = row.match(/return \(\s*<div className=\{`([^`]+)`/)
    expect(root).not.toBeNull()
    expect(classes(root![1])).toEqual(expect.arrayContaining(['flex', 'flex-wrap']))
    // The grade + tag group takes its own line on a phone.
    expect(row).toMatch(/className="order-3 flex w-full min-w-0[^"]*sm:w-auto/)
    const page = readWeb('src/app/onboarding/stpm-grades/page.tsx', 'the STPM grades step')
    floorCount(Array.from(page.matchAll(/<StpmSubjectRow\b/g)), 3, 'STPM rows drawn by the shared row',
      'the compulsory subject, the stream subjects and the elective')
  })

  it('every remove / clear button on the grades steps is a 44 px target', () => {
    const FILES = [
      'src/app/onboarding/grades/page.tsx', 'src/components/SpmResultsBlock.tsx', 'src/components/StpmSubjectRow.tsx',
    ]
    const found: string[] = []
    for (const f of FILES) {
      const src = readWeb(f, 'a grades step')
      for (const m of src.matchAll(/aria-label=\{t\('common\.(remove|clear)'\)\}/g)) {
        const open = src.lastIndexOf('<button', m.index)
        const cls = src.slice(open, m.index! + 200).match(/className="([^"]+)"/)
        expect({ f, cls: cls?.[1] }).toEqual({ f, cls: expect.stringMatching(/(^|\s)h-11(\s|$)/) })
        expect({ f, cls: cls?.[1] }).toEqual({ f, cls: expect.stringMatching(/(^|\s)w-11(\s|$)/) })
        found.push(f)
      }
    }
    floorCount(found, 5, 'remove/clear buttons checked', 'grades: core clear + compact row; SPM block: two; STPM row: one')
  })
})

// TD-311, closed in Mobile M1a (owner: step the hero down on phones in ALL languages). At 48 px the
// longest Tamil word of the hero was wider than a phone, so `/` in Tamil measured 458 px at 360 AND
// 390. At 36 px below `sm` it measures 360 and 390 (Chromium, Mukta Malar) — and desktop is unchanged.
describe('the Home hero and closing call-to-action fit a phone (TD-311)', () => {
  it('the hero heading steps down below sm and keeps its desktop sizes', () => {
    expect(classes(classOf(home, /<h1/))).toEqual(expect.arrayContaining(['text-4xl', 'sm:text-5xl', 'md:text-6xl']))
    expect(classes(classOf(home, /<h1/))).not.toContain('text-5xl')
  })

  it('the closing call-to-action is a box, so a long label wraps INSIDE its button', () => {
    const ctas = Array.from(home.matchAll(/<Link href="\/onboarding\/exam-type" className="([^"]+)"/g), (m) => m[1])
    expect(ctas.length).toBe(2)
    expect(classes(ctas[1])).toEqual(expect.arrayContaining(['inline-block', 'max-w-full']))
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

  it('the /search eligibility toggle may shrink and wrap its text (TD-312)', () => {
    // In Tamil its description made /search 375 px wide at 360: the button was flex-shrink-0.
    const search = readWeb('src/app/search/page.tsx', 'the course search page owns its filter row')
    const row = search.match(/\{\/\* Filter row \*\/\}\s*<div className="([^"]+)">/)
    expect(row).not.toBeNull()
    expect(classes(row![1])).toEqual(expect.arrayContaining(['flex', 'flex-wrap']))
    const toggle = search.match(
      /onClick=\{handleEligibleToggle\}[\s\S]*?className="([^"]+)"\s*>\s*<div className="([^"]+)">[\s\S]*?<div className="([^"]+)">\s*<span[^>]*>\{t\('search\.eligibleOnly'\)\}/)
    expect(toggle).not.toBeNull()
    const [, button, knob, text] = toggle!
    expect(classes(button)).toEqual(expect.arrayContaining(['min-w-0', 'max-w-full']))
    expect(classes(button)).not.toContain('flex-shrink-0')
    expect(classes(button)).not.toContain('shrink-0')
    expect(classes(knob)).toContain('shrink-0')
    expect(classes(text)).toContain('min-w-0')
  })

  it('"Log in" on /get-started stays on one line', () => {
    const page = readWeb('src/app/get-started/page.tsx', 'the sign-up chooser has its own Log in button')
    const btn = page.match(/className="([^"]+)"\s*>\s*\{t\('header\.login\.label'\)\}/)
    expect(btn).not.toBeNull()
    expect(classes(btn![1])).toContain('whitespace-nowrap')
  })
})
