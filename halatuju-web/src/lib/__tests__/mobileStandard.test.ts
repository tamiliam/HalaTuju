/**
 * The Mobile Standard's static guards (Mobile M0, 2026-10-31). The rules: `docs/mobile-standard.md`.
 *
 * Students use HalaTuju on phones almost all the time. Each block below counts how often the code
 * breaks one rule that can be read from source, and holds that count to a FLOOR.
 *
 * ⚠ EVERY FLOOR IS A RATCHET THAT MAY ONLY GO DOWN. It is today's exact count of offenders, not a
 * target. When you fix one, the count drops below the floor and this suite tells you to LOWER the
 * number — do it in the same change, so the room you made cannot be spent by the next person. Never
 * RAISE a floor: a new offender is fixed, not counted. (The same rule `code-standards.json` keeps.)
 * Every failure prints the offenders, so you can see exactly which line to change.
 *
 * What is scanned: every `.ts`/`.tsx` under `src/`, less
 *   - tests (`__tests__/`, `*.test.*`) and `src/test/` — they hold examples of the very patterns
 *     they forbid;
 *   - the design sandbox (`src/sandbox/`, `*.sandbox.tsx`) — compiled OUT of production
 *     (next.config.js), and its picker chrome is not a product screen. The REAL screens it mounts
 *     are scanned where they live.
 *
 * What a source scan cannot see — inherited font sizes, computed tap sizes, real overflow — the
 * browser check `npm run mobile-check` measures. The reader's own limits are in `src/test/mobileScan.ts`.
 */
import * as fs from 'fs'
import * as path from 'path'
import { readWeb, walkFloor, WEB_ROOT } from '@/test/sourceGuard'
import {
  attr, blankComments, classText, constResolver, literalsIn, literalsWithIndex, openTags, scanFiles,
  tokens, where, withoutLiterals,
  type Offender, type Scanned,
} from '@/test/mobileScan'
import { MOBILE_CLASS, routeOfPage } from '@/lib/mobileClass'
import { sandboxSlugs } from '../../../mobile-check/targets'

// ── The corpus ────────────────────────────────────────────────────────────────────────────────
/** 627 `.ts`/`.tsx` files under src/ on 2026-10-31; a MINIMUM, so new files stay green. */
const WHY_SRC = 'every rule below counts offenders across the whole web source; a walk that found '
  + 'nothing would count zero and pass for ever'
const ALL = walkFloor(path.join(WEB_ROOT, 'src'), 600, WHY_SRC, { exts: ['.ts', '.tsx'] })
const isExcluded = (rel: string) => /(^|\/)__tests__\//.test(rel) || /\.test\.tsx?$/.test(rel)
  || rel.startsWith('src/test/') || rel.startsWith('src/sandbox/') || rel.endsWith('.sandbox.tsx')
const FILES: Scanned[] = scanFiles(ALL).filter((f) => !isExcluded(f.rel))
const TSX = FILES.filter((f) => f.rel.endsWith('.tsx'))
const resolve = constResolver(FILES)

/** The assertion every ratchet shares: at or under the floor, with the offenders in the message. */
function ratchet(name: string, offenders: Offender[], floor: number): void {
  const n = offenders.length
  const listing = offenders.map((o) => `    ${o}`).join('\n')
  if (n > floor) {
    throw new Error(`${name}: ${n} found, the floor is ${floor}. A NEW offender — fix it, never `
      + `raise the floor (docs/mobile-standard.md says how).\n${listing}`)
  }
  if (n < floor) {
    throw new Error(`${name}: ${n} found, the floor is ${floor}. You fixed some — LOWER the floor `
      + `in mobileStandard.test.ts to ${n} in this same change, so the room cannot be re-spent.\n${listing}`)
  }
}

describe('the corpus this file depends on is really there', () => {
  test('hundreds of source files, most of them components', () => {
    expect(FILES.length).toBeGreaterThanOrEqual(500)
    expect(TSX.length).toBeGreaterThanOrEqual(300)
  })
})

// ── Rule 2: text fields at 16 px on phones ────────────────────────────────────────────────────
/**
 * A text field under 16 px makes iPhone Safari ZOOM THE PAGE when it is tapped, and the page stays
 * zoomed. The offence is a small size that APPLIES ON A PHONE: `text-sm`, `text-xs`, `text-[<16px]`
 * (also `text-[length:14px]`, `text-sm/6`, `!text-sm`), bare or behind a variant that still applies
 * at phone width — `max-md:`, `max-sm:`, `max-[…]:`, and state variants such as `focus:` or `dark:`
 * (a field that shrinks on focus zooms on tap just the same). A MIN-width breakpoint (`sm:`, `md:`,
 * `lg:`, `xl:`, `2xl:`, `min-[…]:`) starts above every phone in the standard, so `md:text-sm` is
 * fine; so are `placeholder:`/`file:` sizes, which do not size the field. Checkboxes, radios,
 * hidden, file, range and button-like inputs take no typing and are skipped; an `type={…}`
 * expression counts as text unless every literal in it is one of those.
 *
 * ⚠ LIMITS (best effort, stable, honest). A control with NO size class inherits its parent's size
 * (Tailwind's preflight sets `font-size: 100%`), which only the browser check can see. A class
 * built from props or a constant the reader cannot resolve is not judged.
 */
const NOT_TEXT = new Set(['checkbox', 'radio', 'hidden', 'file', 'range', 'color', 'submit', 'button',
  'reset', 'image'])
/** Variants that switch a class OFF at phone width, or point it at something other than the field. */
const NOT_ON_PHONE = /^(?:sm|md|lg|xl|2xl|min-\[[^\]]*\]|placeholder|file)$/

/** True when this class token sets a font size under 16 px that is in force on a phone. */
function smallOnPhone(token: string): boolean {
  // Split variants on `:` OUTSIDE brackets — `text-[length:14px]` holds one inside its value.
  const parts = token.split(/:(?![^[]*\])/)
  const utility = (parts.pop() ?? '').replace(/^!/, '')
  if (parts.some((v) => NOT_ON_PHONE.test(v.replace(/^!/, '')))) return false
  const size = utility.replace(/\/[\w.[\]-]+$/, '')            // drop a `/leading` suffix
  if (size === 'text-xs' || size === 'text-sm') return true
  const m = size.match(/^text-\[(?:length:)?(\d*\.?\d+)(px|rem|em)\]$/)
  if (!m) return false
  const n = parseFloat(m[1])
  return m[2] === 'px' ? n < 16 : n < 1
}

function isTextEntry(tag: { name: string; attrs: string }): boolean {
  if (tag.name !== 'input') return true
  const type = attr(tag.attrs, 'type')
  if (!type) return true
  if ('literal' in type) return !NOT_TEXT.has(type.literal)
  const lits = literalsIn(type.expr)
  return !(lits.length > 0 && lits.every((l) => NOT_TEXT.has(l)))
}

describe('rule 2 — text fields are 16 px on phones (no iOS zoom)', () => {
  const controls = TSX.flatMap((f) => ['input', 'select', 'textarea']
    .flatMap((name) => openTags(f.code, name).map((tag) => ({ f, tag }))))
    .filter(({ tag }) => isTextEntry(tag))

  test('the reader finds the text-entry controls at all', () => {
    // ~300 on 2026-10-31. A reader that stopped finding tags would report no offenders.
    expect(controls.length).toBeGreaterThanOrEqual(250)
  })

  /**
   * ⚠ SINCE MOBILE M1a THE FIX IS ONE RULE, SO THE GUARD CHANGED SHAPE. Before M1a this test counted
   * every field with a small size on a phone (floor 208 after the M0 review, 182 before it) and the
   * plan was to fix them one by one. M1a fixed them all at once: a rule in `globals.css` sets 16 px
   * on every text-entry control below `md`, and it outranks any ordinary utility. Counting `text-sm`
   * fields now would count fields that are NOT small on a phone, so the guard is two things instead:
   *   1. the rule exists, below `md`, OUTSIDE every `@layer` (inside `@layer base` it would lose to
   *      `text-sm` — the very thing it exists to beat), and with the exclusions that keep it from
   *      touching checkboxes, radios and file pickers;
   *   2. the sizes it CANNOT beat stay at zero — an `!important` small size (`!text-sm`) wins over
   *      any selector without `!important`, so a field carrying one would zoom again.
   * The browser check measures the outcome on every page: `smallInputs` is 0 in every cell.
   */
  test('the global 16 px rule exists, below md AND on touch screens, outside every @layer', () => {
    const css = readWeb('src/app/globals.css', 'the one rule that makes text fields 16 px on phones')
      .replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, ' '))
    // `pointer: coarse` too: an iPhone held sideways is 844–932 px wide and still zooms (M1 close review).
    const at = css.indexOf('@media (max-width: 767.98px), (pointer: coarse)')
    expect(at).toBeGreaterThan(-1)
    let depth = 0
    for (const c of css.slice(0, at)) depth += c === '{' ? 1 : c === '}' ? -1 : 0
    expect(`brace depth before the rule: ${depth}`).toBe('brace depth before the rule: 0')
    const rule = css.slice(at, css.indexOf('\n}', at))
    expect(rule).toMatch(/font-size:\s*16px/)
    for (const t of ['checkbox', 'radio', 'range', 'file', 'hidden']) expect(rule).toContain(`[type='${t}']`)
    expect(rule).toMatch(/^\s*select:not/m)
    expect(rule).toMatch(/^\s*textarea:not/m)
  })

  test('no text field carries a small size the global rule cannot beat (!important)', () => {
    const offenders = controls.flatMap(({ f, tag }) => {
      const small = tokens(classText(f, tag, resolve))
        .find((t) => smallOnPhone(t) && /(^|:)!/.test(t))
      return small ? [where(f, tag.start, `<${tag.name} … ${small}`)] : []
    })
    // Mobile M1a: was 208 small-text fields (M0 review: reader fixed, was 182); the global rule
    // covers all of those, so this counts only what it cannot cover. 0 on 2026-10-31.
    ratchet('text fields with an !important small font', offenders, 0)
  })
})

// ── Rule 9: file inputs are sr-only, never hidden ─────────────────────────────────────────────
/**
 * Some phone browsers will not open the picker for a `display: none` input when its label is
 * tapped. `sr-only` keeps it in the layout, invisible — the pattern in
 * `src/components/ScholarshipDocuments/cards.tsx`. Counts `type="file"` inputs whose class carries
 * `hidden` (unprefixed).
 */
describe('rule 9 — file inputs are sr-only, never hidden', () => {
  test('hidden file inputs: at or under the floor', () => {
    const files = TSX.flatMap((f) => openTags(f.code, 'input').map((tag) => ({ f, tag })))
      .filter(({ tag }) => {
        const type = attr(tag.attrs, 'type')
        return !!type && 'literal' in type && type.literal === 'file'
      })
    expect(files.length).toBeGreaterThanOrEqual(5)
    const offenders = files
      .filter(({ f, tag }) => tokens(classText(f, tag, resolve)).includes('hidden'))
      .map(({ f, tag }) => where(f, tag.start, '<input type="file" … hidden'))
    // Mobile M1a: 6 -> 0. All six moved to `sr-only` (the two opened by a button's ref.click()
    // also take tabIndex={-1}, so the invisible input is not a second, silent tab stop).
    ratchet('file inputs hidden with `hidden`', offenders, 0)
  })
})

// ── Rule 10: keyboards and autofill — phone fields take the NATIONAL number ──────────────────
/**
 * Every phone field here holds a LOCAL number ("012-345 6789"; the +60 is a fixed prefix or added
 * by the server), and `formatPhone` keeps 11 digits. `autoComplete="tel"` makes the browser fill
 * the INTERNATIONAL form ("+60 12-345 6789"): the profile page then rejected the number the browser
 * itself filled, and an 011 number lost its last digit (M1b adversarial review). So: `tel-national`
 * for the person's own number, `off` for somebody else's (an admin inviting a source must not get
 * their OWN number filled in).
 */
describe('rule 10 — a phone field never autofills the international number', () => {
  test('no autoComplete="tel" anywhere in the web source', () => {
    const offenders = TSX.flatMap((f) => openTags(f.code, 'input')
      .filter((tag) => {
        const ac = attr(tag.attrs, 'autoComplete')
        return !!ac && 'literal' in ac && ac.literal === 'tel'
      })
      .map((tag) => where(f, tag.start, '<input autoComplete="tel"')))
    ratchet('phone fields that autofill the international number', offenders, 0)
  })
})

// ── Rule 9 (Mobile M4): a file picker never forces the camera ─────────────────────────────────
/**
 * `capture` on a file input makes a phone open the CAMERA only — no photo library, no Files — so a
 * student could not upload the PDF payslip or EPF statement she downloaded. The phone's own chooser
 * already offers "Take Photo". Positive guard: none, anywhere.
 */
describe('rule 9 — a file input never forces the camera', () => {
  test('no `capture` on any file input', () => {
    const offenders = TSX.flatMap((f) => openTags(f.code, 'input')
      .filter((tag) => /\bcapture\b/.test(tag.attrs))
      .map((tag) => where(f, tag.start, '<input … capture')))
    ratchet('file inputs that force the camera', offenders, 0)
  })
})

// ── Rule 10 (Mobile M4): the apply form keeps its progress, and a press sends one answer ──────
/**
 * The apply form is the long form rule 10 was written for. Its draft lives in `lib/applyDraft.ts`
 * (owner: this tab only — what it holds and when it goes is pinned in `applyDraft.test.ts`). These
 * read the PAGE, so a refactor that drops the draft or a door's guard turns this red, and they read
 * BOTH places the furniture lives (the page and `ApplyStepper`) — lessons.md: when code moves, the
 * guard follows it AND keeps watching where it must not come back.
 */
describe('rule 10 — the apply form keeps its progress', () => {
  const page = readWeb('src/app/scholarship/apply/page.tsx', 'the apply form whose draft and doors rule 10 pins')
  const stepper = readWeb('src/components/scholarship/ApplyStepper.tsx', 'where the Back / Continue bar moved (Mobile M4)')

  test('the page keeps a draft, restores it, and deletes it once sent', () => {
    expect(page).toMatch(/useApplyDraft\(form, uid, gift\.code, tab,/)
    expect(page).toMatch(/readApplyDraft\(\{ uid, programme: gift\.code \}\)/)
    expect(page).toMatch(/await submitScholarshipApplication\([^)]*\)\s*\n\s*setSent\(true\); clearApplyDraft\(\)/)
  })

  test('the submit handler sends nothing while a submit is in flight, and Enter before the end is Next', () => {
    const handler = page.slice(page.indexOf('const handleSubmit'), page.indexOf('const payload'))
    expect(handler).toMatch(/if \(submitting\) return/)
    expect(handler).toMatch(/if \(tab !== TAB_ORDER\[TAB_ORDER\.length - 1\]\) \{ goNext\(\); return \}/)
  })

  test('Back / Continue is a sticky phone bar clear of the home bar — and the old icon tab bar is gone', () => {
    expect(stepper).toMatch(/sticky bottom-0[^"]*pb-\[max\(0\.75rem,env\(safe-area-inset-bottom\)\)\]/)
    expect(page).toContain('<ApplyFooter')
    expect(page).not.toMatch(/text-\[10px\]/)          // the 6 × 56 px bar's labels must not come back
    expect(page).not.toMatch(/function TabIcon/)
  })
})

/**
 * The student's consent / money screens never ask with the browser's own `confirm` (a box that
 * looks like a phishing prompt on a phone, and cannot be styled, translated or tested as a sheet):
 * they ask in the shared `Sheet`. ONE exemption, named: the documents tab's fallback when the remove
 * sheet's lazy chunk cannot load (lessons.md: a lazy way out needs an eager one).
 */
const CONFIRM_EXEMPT: Record<string, string> = {
  'src/components/ScholarshipDocuments.tsx': 'the remove sheet is lazy; if its chunk fails, this asks instead',
}
describe('student scholarship screens ask in a Sheet, never window.confirm', () => {
  test('no window.confirm in the student scholarship screens (one named fallback)', () => {
    const student = FILES.filter((f) => /^src\/(app\/scholarship\/|components\/(Scholarship|ActionCentre|scholarship\/))/.test(f.rel))
    expect(student.length).toBeGreaterThanOrEqual(20)
    const offenders = student.filter((f) => /window\.confirm\(/.test(blankComments(f.code)) && !(f.rel in CONFIRM_EXEMPT))
      .map((f) => `${f.rel}: window.confirm`)
    expect(offenders).toEqual([])
    for (const rel of Object.keys(CONFIRM_EXEMPT)) expect(readWeb(rel, 'a named exemption must still exist')).toContain('window.confirm(')
  })
})

// ── Rule 15 (owner, 2026-11-02): one box level; sections on phones ─────────────────────────────
/**
 * On a phone a card is a plain full-width SECTION and nothing inside it is boxed again (the Grab
 * comparison). The classes live in ONE place, `src/lib/phoneSection.ts`. Swept so far: the Mobile M4
 * screens below — a white bordered card class written by hand there (instead of PHONE_SECTION) fails.
 * The next sprint adds the other student pages to this list.
 */
const RULE15_SWEPT = [
  'src/app/scholarship/apply/page.tsx', 'src/app/scholarship/award/page.tsx',
  'src/app/scholarship/application/page.tsx', 'src/components/ScholarshipNextSteps.tsx',
  'src/components/ActionCentre.tsx', 'src/components/scholarship/PostAwardTasks.tsx',
  // Mobile M4b: Dashboard, Search, the course pages, Profile, Saved and Settings.
  'src/app/dashboard/page.tsx', 'src/components/HigherRouteDegrees.tsx', 'src/app/search/page.tsx',
  'src/app/course/[id]/page.tsx', 'src/app/stpm/[id]/page.tsx', 'src/components/CourseHeader.tsx',
  'src/components/CourseDetailShared.tsx', 'src/components/CareerPathways.tsx', 'src/components/SpecialConditions.tsx',
  'src/components/RequirementsCard.tsx', 'src/components/course/PreUInstitutions.tsx', 'src/app/profile/page.tsx',
  'src/components/profile/CourseInterestsSection.tsx', 'src/app/saved/page.tsx', 'src/app/settings/page.tsx',
  // Mobile M4c: My Bursary and its tabs, Home, the scholarship landing, the report, the info and legal pages,
  // the pathway pages, onboarding (and the scholarship's own) and both quizzes.
  'src/app/scholarship/bursary/page.tsx', 'src/components/bursary/BursaryFunds.tsx',
  'src/components/bursary/BursaryContract.tsx', 'src/components/bursary/BursaryLetters.tsx',
  'src/components/bursary/BursaryMentoring.tsx', 'src/components/bursary/BursaryNews.tsx',
  'src/components/bursary/BursarySurveys.tsx', 'src/app/page.tsx', 'src/app/scholarship/page.tsx',
  'src/app/about/page.tsx', 'src/app/contact/page.tsx', 'src/app/cookies/page.tsx',
  'src/app/privacy/page.tsx', 'src/app/terms/page.tsx', 'src/app/get-started/page.tsx',
  'src/app/pathway/matric/page.tsx', 'src/app/pathway/stpm/page.tsx', 'src/app/onboarding/exam-type/page.tsx',
  'src/app/onboarding/grades/page.tsx', 'src/app/onboarding/higher-grades/page.tsx',
  'src/app/onboarding/stpm-grades/page.tsx', 'src/app/onboarding/profile/page.tsx',
  'src/app/scholarship/onboarding/page.tsx', 'src/app/quiz/page.tsx', 'src/app/stpm/quiz/page.tsx',
  // Mobile M5: the sponsor portal — its shell, My Giving, one pool student, My Account, Trust, the landing.
  'src/components/sponsor/SponsorShell.tsx', 'src/app/sponsor/(portal)/page.tsx',
  'src/app/sponsor/(portal)/students/[id]/page.tsx', 'src/app/sponsor/(portal)/account/page.tsx',
  'src/app/sponsor/(portal)/trust/page.tsx', 'src/components/SponsorLanding.tsx',
]
/** Swept too, but with no section or gutter of their own (so no import): rows and pills inside one. */
const RULE15_SWEPT_PARTS = ['src/components/PathwayCards.tsx', 'src/components/FamilyRosterFields.tsx',
  'src/components/SpmResultsBlock.tsx', 'src/components/StpmSubjectRow.tsx', 'src/components/ReportView.tsx',
  // Mobile M5: sponsor screens with no section or gutter of their own.
  'src/app/sponsor/(portal)/students/page.tsx', 'src/app/sponsor/(portal)/my-students/[id]/page.tsx',
  'src/components/sponsors/SponsorTermsWizard.tsx', 'src/components/sponsor/JourneyLine.tsx',
  'src/components/SponsorDetailsForm.tsx',
  'src/app/sponsor/login/page.tsx', 'src/app/sponsor/register/page.tsx', 'src/app/sponsor/auth/reset/page.tsx',
  // Mobile M6a: the console's everyday screens — the case list, the sign-in screens, Guide, FAQ, the
  // Organisation page and the Profile cards (one class constant), and the 404.
  'src/app/admin/scholarship/page.tsx', 'src/app/admin/login/page.tsx', 'src/app/admin/set-password/page.tsx',
  'src/app/admin/auth/callback/page.tsx', 'src/app/admin/guide/page.tsx', 'src/app/admin/faq/page.tsx',
  'src/app/admin/organisation/page.tsx', 'src/components/adminProfile/shared.tsx', 'src/app/admin/not-found.tsx',
  'src/components/admin/CaseListPhoneTools.tsx',
  // Mobile M6b: the cockpit — the case page, its panels, the decision bar.
  'src/app/admin/scholarship/[id]/view.tsx', 'src/app/admin/scholarship/[id]/view/ApplicantCards.tsx',
  'src/app/admin/scholarship/[id]/view/AssignAndWitness.tsx',
  'src/app/admin/scholarship/[id]/view/BlockersPanel.tsx',
  'src/app/admin/scholarship/[id]/view/CockpitHeader.tsx', 'src/app/admin/scholarship/[id]/view/DecisionBar.tsx',
  'src/app/admin/scholarship/[id]/view/DecisionCard.tsx',
  'src/app/admin/scholarship/[id]/view/DocumentsDrawer.tsx',
  'src/app/admin/scholarship/[id]/view/GeneratedProfile.tsx',
  'src/app/admin/scholarship/[id]/view/InterviewPanels.tsx',
  'src/app/admin/scholarship/[id]/view/OrgRejectPanel.tsx',
  'src/app/admin/scholarship/[id]/view/OutstandingPanel.tsx',
  'src/app/admin/scholarship/[id]/view/PostAwardPanels.tsx', 'src/app/admin/scholarship/[id]/view/QcPanel.tsx',
  'src/app/admin/scholarship/[id]/view/RateAndEstimate.tsx',
  'src/app/admin/scholarship/[id]/view/VerificationVerdict.tsx',
  'src/app/admin/scholarship/[id]/view/shared.tsx']
/** Class constants that only ever dress a CONTROL (a choice button), so the card check passes them — by name. */
const CONTROL_CONSTS: Record<string, string[]> = {
  'src/app/onboarding/exam-type/page.tsx': ['const CHOICE'],   // the three results-route choice BUTTONS
  'src/app/onboarding/higher-grades/page.tsx': ['const pill'],   // the qualification / institution choice BUTTONS
}
describe('rule 15 — one box level; sections on phones', () => {
  test('the swept screens draw no hand-written white card (they use PHONE_SECTION)', () => {
    const code = (rel: string) => readWeb(rel, 'a rule-15 screen').split('\n').filter((l) => !/^\s*(\/\/|\*)/.test(l)).join('\n')
    // A white card: ONE class string holding rounded-xl / -2xl and the card ground (`bg-ground-0`), in any
    // order, unprefixed — WITH OR WITHOUT a border (M4c review: My Bursary's cards were borderless shadow cards
    // and the `border`-token test could not see them, nor a `border-2` card). M4b: one string, any order.
    // A genuine CONTROL keeps its box (the rule's own exception) — judged by the ELEMENT the string sits on
    // (a button, a link, a field, a label), never by its size (M4c review: a `min-h-11` exemption let any
    // 44 px card through), or by a named class constant that only ever dresses a control (CONTROL_CONSTS).
    const card = (s: string) => {
      const t = s.split(/[\s'"`{}$()]+/)   // never on `:` — `md:bg-ground-0` is a desktop-only box
      return t.some((x) => /^rounded-(xl|2xl)$/.test(x)) && t.includes('bg-ground-0')
    }
    const CONTROL_TAG = /^(button|a|Link|input|select|textarea|label|summary)$/
    /** The JSX tag a class string sits on (`<button className="…">`), or `const NAME` for a constant. */
    const owner = (src: string, at: number) => {
      const before = src.slice(0, at)
      const decl = before.match(/const (\w+) = (\([^)]*\) => )?$/)   // a constant, or a class-name maker
      if (decl) return `const ${decl[1]}`
      const tags = Array.from(before.matchAll(/<([A-Za-z][\w.]*)\b/g))
      const last = tags[tags.length - 1]
      if (!last) return ''
      // Still inside that opening tag: no `>` since it, other than an arrow's `=>`.
      return /(?<!=)>/.test(before.slice(last.index! + last[0].length)) ? '' : last[1]
    }
    const offenders = [...RULE15_SWEPT, ...RULE15_SWEPT_PARTS].flatMap((rel) => {
      const src = code(rel)
      return Array.from(src.matchAll(/"([^"\n]*)"|'([^'\n]*)'|`([^`]*)`/g))
        .filter((m) => card(m[1] ?? m[2] ?? m[3] ?? ''))
        .map((m) => owner(src, m.index!))
        .filter((o) => !CONTROL_TAG.test(o) && !(CONTROL_CONSTS[rel] ?? []).includes(o))
        .map((o) => `${rel}: a white card on ${o || 'an unknown element'}`)
    })
    expect(offenders).toEqual([])
    // No bare 24 px page gutter on a phone: a `container` line carries PHONE_GUTTER (px-4; px-6 from md).
    const gutters = RULE15_SWEPT.flatMap((rel) => code(rel).split('\n')
      .filter((l) => /\bcontainer\b/.test(l) && /(?<![\w:-])px-6\b/.test(l)).map((l) => `${rel}: ${l.trim()}`))
    expect(gutters).toEqual([])
    for (const rel of RULE15_SWEPT) expect(readWeb(rel, 'a rule-15 screen')).toContain("from '@/lib/phoneSection'")
  })
  test('row dividers are phones-only (max-md:), never `divide-y … md:divide-y-0`', () => {
    // M4b review: Tailwind's divide selector (`> :not([hidden]) ~ :not([hidden])`) beats an item's own
    // `md:border`, so `md:divide-y-0` stripped every md box after the first of its top and bottom border,
    // and an unprefixed `divide-ground-*` recoloured them at every width. Dividers are `max-md:` only.
    const src = readWeb('src/lib/phoneSection.ts', 'the one home of rule 15')
    const rows = (src.match(/PHONE_ROWS = '([^']+)'/) ?? [])[1] ?? ''
    expect(rows.split(' ').filter((t) => /^divide-/.test(t))).toEqual([])
    expect(rows).toMatch(/max-md:divide-y\b/)
    const files = [...RULE15_SWEPT, ...RULE15_SWEPT_PARTS, 'src/lib/phoneSection.ts', 'src/components/ScholarshipDocuments.tsx']
    const offenders = files.filter((rel) => /\bmd:divide-y-0\b/.test(readWeb(rel, 'a rule-15 screen')
      .split('\n').filter((l) => !/^\s*(\/\/|\*)/.test(l)).join('\n')))
    expect(offenders).toEqual([])
  })
  test('the sections are a card from md, and plain (no border, no rounding) below it', () => {
    const src = readWeb('src/lib/phoneSection.ts', 'the one home of rule 15')
    const section = (src.match(/PHONE_SECTION = '([^']+)'/) ?? [])[1] ?? ''
    const noGap = (src.match(/PHONE_SECTION_NO_GAP = '([^']+)'/) ?? [])[1] ?? ''
    const flat = (src.match(/PHONE_SECTION_FLAT = '([^']+)'/) ?? [])[1] ?? ''
    for (const t of [...section.split(' '), ...noGap.split(' '), ...flat.split(' ')]) {
      if (/^(rounded|shadow|bg-|p-)/.test(t)) throw new Error(`PHONE_SECTION boxes a phone too: ${t}`)
    }
    // The no-gap section is the same section with no margin of its own (M4b: the desktop keeps its spacing).
    expect(noGap).toBe(section.replace(' md:mb-4', ''))
    expect(section).toMatch(/md:rounded-2xl/)
    // M4c: the borderless card (My Bursary) is the same phone section, no border and no margin from md.
    expect(flat).toMatch(/^border-b border-ground-100 py-4 /)
    expect(flat.split(' ')).toEqual(expect.arrayContaining(['md:border-0', 'md:rounded-2xl', 'md:bg-ground-0', 'md:shadow-sm']))
    expect(flat).not.toMatch(/md:mb-/)
    expect(src).toMatch(/PHONE_GUTTER = 'px-4 md:px-6'/)
  })
})

// ── Rule 3 (owner, 2026-11-02, M4c follow-up): the quizzes on a phone ──────────────────────────
/**
 * Ten 10 px question dots cannot be 44 px targets on a phone, so BOTH quizzes hide the dot row below
 * `md` and move with a 44 px Next (phones only) and Previous; the header's progress bar and "Question n
 * of N" say where she is. From `md` the dots stay. `/quiz` is render-tested in `app/quiz/page.test.tsx`;
 * this pins the same shape in both files.
 */
describe('rule 3 — the quizzes trade the dot row for Next on a phone', () => {
  for (const rel of ['src/app/quiz/page.tsx', 'src/app/stpm/quiz/page.tsx']) {
    test(rel, () => {
      const src = readWeb(rel, 'a quiz page')
      expect(src).toMatch(/<div className="hidden md:flex justify-center gap-2 mb-6" data-testid="quiz-dots">/)
      expect(src).toMatch(/className="btn-primary min-h-11 md:hidden[^"]*"\s+data-testid="quiz-next"/)
      expect(src).toMatch(/disabled=\{!currentAnswered\}/)
      expect(src).toContain("t('discovery.quizNext')")
      expect(src).toContain("import '@/lib/messagesDiscovery'")
      expect(src).toMatch(/t\('quiz\.questionOf'/)
    })
  }
})

// ── Rule 11 (Mobile M4b): the student tab bar, and ONE bottom bar at a time ──────────────────
/**
 * The phone's tab bar (`StudentTabBar`) is mounted by the student header only, and gives way to a
 * page's own bottom bar through CSS: every such bar carries `data-page-bar`, and `globals.css` hides
 * the tabs while one is on the page (the owner's swap rule). A page bar WITHOUT the marker would sit
 * on top of the fixed tabs — two bars, the main action covered — so an unmarked one fails here.
 */
const STUDENT_SCOPE = (rel: string) => /^src\/(app|components)\//.test(rel)
  && !/^src\/(app|components)\/(admin|sponsor)\//.test(rel)
const PINNED_BOTTOM = (cls: string) => {
  const t = cls.split(/\s+/)
  // Any foot offset (`bottom-0`, `bottom-2`, `bottom-[max(…)]`), unprefixed: a phone draws it (M4b review).
  // (`hidden` unprefixed: not drawn on a phone at all — the saved page's desktop compare bar.)
  return t.some((x) => /^bottom-(\d|\[|px)/.test(x)) && (t.includes('sticky') || t.includes('fixed')) && !t.includes('hidden')
}
/** Pinned to the foot but not a bar, with the reason. */
const NOT_A_PAGE_BAR: Record<string, string> = {
  'src/components/Toast.tsx': 'the toast stack floats ABOVE every bar (--bottom-bar); it is not one',
}
describe('rule 11 — the student tab bar gives way to a page\'s own bar', () => {
  test('every bar pinned to the foot of a student screen carries data-page-bar', () => {
    const bars: string[] = []
    const offenders: Offender[] = []
    for (const f of TSX.filter((x) => STUDENT_SCOPE(x.rel) && !(x.rel in NOT_A_PAGE_BAR))) {
      for (const name of ['div', 'nav', 'footer', 'section', 'form', 'aside', 'header']) {
        for (const tag of openTags(f.code, name)) {
          if (!PINNED_BOTTOM(classText(f, tag, resolve))) continue
          bars.push(f.rel)
          if (!/(^|\s)data-page-bar(\s|=|$)/.test(tag.attrs)) offenders.push(where(f, tag.start, tag.attrs))
        }
      }
    }
    // The five of M4b: course Save, saved compare, apply Back / Continue, award sign, post-award steps.
    expect(bars.length).toBeGreaterThanOrEqual(5)
    expect(offenders).toEqual([])
    for (const rel of Object.keys(NOT_A_PAGE_BAR)) expect(readWeb(rel, 'a named exemption must still exist')).toMatch(/\bfixed\b[^"`]*\bbottom-/)
  })
  test('the tab bar is mounted by the student header only, which a flow or the sponsor side turns off', () => {
    const users = FILES.filter((f) => /from '(@\/components|\.)\/StudentTabBar'/.test(f.code)).map((f) => f.rel)
    expect(users).toEqual(['src/components/AppHeader.tsx'])
    expect(readWeb('src/components/AppHeader.tsx', 'the student header')).toMatch(/\{tabs && <StudentTabBar \/>\}/)
    for (const rel of ['src/app/scholarship/onboarding/page.tsx', 'src/components/SponsorLanding.tsx']) {
      expect(readWeb(rel, 'a page that keeps the header but not the tabs')).toContain('<AppHeader tabs={false} />')
    }
    // Onboarding and the quizzes draw no student header at all, so no tabs.
    const flows = FILES.filter((f) => /^src\/app\/(onboarding|quiz|stpm\/quiz)\//.test(f.rel))
    expect(flows.length).toBeGreaterThanOrEqual(5)
    expect(flows.filter((f) => /<AppHeader\b/.test(f.code)).map((f) => f.rel)).toEqual([])
  })
  test('its words are existing CORE keys (no new string) and the organisation\'s own short name', () => {
    const src = readWeb('src/components/StudentTabBar.tsx', 'the tab bar')
    const keys = Array.from(src.matchAll(/\bt\('([\w.]+)'\)/g)).map((m) => m[1])
    expect(keys.sort()).toEqual(['common.dashboard', 'common.menu', 'common.saved', 'search.nav'])
    const en = JSON.parse(readWeb('src/messages/en.json', 'the English catalogue'))
    for (const k of keys) expect(k.split('.').reduce((o: Record<string, unknown>, p) => o?.[p] as never, en)).toEqual(expect.any(String))
    // `common` and `search` are core namespaces: neither is cut into a slice.
    const slicer = readWeb('scripts/messages-slice-loader.js', 'the slice loader')
    expect(slicer).not.toMatch(/['"](common|search)['"]/)
    expect(src).toContain('orgShortName')
  })
  test('globals.css: phones only, never without :has(), swapped by a page bar, hidden while typing, the page padded, the toast lifted', () => {
    const css = readWeb('src/app/globals.css', 'the stylesheet').replace(/\/\*[\s\S]*?\*\//g, '')
    expect(css).toMatch(/\[data-tab-bar\] \{\s*display: none;/)
    const block = css.slice(css.indexOf('@supports selector(:has(*))'))
    expect(block.length).toBeGreaterThan(30)
    expect(block).toMatch(/@media \(max-width: 767\.98px\)/)
    expect(block).toMatch(/html:not\(:has\(\[data-page-bar\]\)\) \[data-tab-bar\] \{\s*display: grid;/)
    expect(block).toMatch(/textarea, \[contenteditable='true'\]\):focus\) \[data-tab-bar\] \{\s*display: none;/)
    // Not a select: Android keeps it focused after the pick, and the bar would stay away (M4b review).
    expect(block).not.toMatch(/\bselect\b[^{]*:focus\) \[data-tab-bar\]/)
    // The bar's full height (home-bar inset included), so the toast keeps its gap above it on an iPhone.
    expect(block).toMatch(/--bottom-bar: calc\(4rem \+ env\(safe-area-inset-bottom\)\);/)
    expect(block).toMatch(/padding-bottom: calc\(4rem \+ env\(safe-area-inset-bottom\)\);/)
    expect(css).toMatch(/\[data-tab-bar\] a \{[^}]*min-height: 4rem;/)
    expect(css).toMatch(/\[data-tab-bar\] \{[^}]*padding-bottom: env\(safe-area-inset-bottom\);/)
  })
})

// ── Rule 11 (Mobile M5): the sponsor's own tab bar ───────────────────────────────────────────────
/**
 * The sponsor portal's phone navigation is `SponsorTabBar` (three tabs), drawn ONLY by `SponsorShell`,
 * which ONLY the portal layout (and the design sandbox) mounts. It is the student bar's PATTERN — the
 * same `data-tab-bar` CSS — never the student bar: `StudentTabBar` must not reach a sponsor screen. The
 * student guard above skips `src/(app|components)/sponsor/`, so the sponsor side is checked here: every
 * bar pinned to the foot of a sponsor screen carries `data-page-bar`, or it would sit on the tabs.
 */
const SPONSOR_SCOPE = (rel: string) => /^src\/(app\/sponsor|components\/sponsors?)\//.test(rel)
  || /^src\/components\/Sponsor\w*\.tsx$/.test(rel)
describe('rule 11 — the sponsor tab bar', () => {
  test('mounted by the portal shell only; the shell by the portal layout (and the sandbox) only', () => {
    const importers = (mod: string) => FILES.filter((f) => new RegExp(`from '@/components/sponsor/${mod}'`).test(f.code)).map((f) => f.rel).sort()
    expect(importers('SponsorTabBar')).toEqual(['src/components/sponsor/SponsorShell.tsx'])
    expect(importers('SponsorShell')).toEqual(['src/app/sponsor/(portal)/layout.tsx'])
    // (The design sandbox mounts it too; the sandbox is outside this walk, so it is read by name.)
    expect(readWeb('src/sandbox/sponsorM5Surfaces.tsx', 'the M5 surfaces')).toMatch(/from '@\/components\/sponsor\/SponsorShell'/)
    const shell = readWeb('src/components/sponsor/SponsorShell.tsx', 'the sponsor shell')
    expect(shell).toMatch(/\{nav && <SponsorTabBar path=\{here\} \/>\}/)
  })
  test('never the student bar on a sponsor screen', () => {
    const sponsorSide = FILES.filter((f) => SPONSOR_SCOPE(f.rel))
    expect(sponsorSide.length).toBeGreaterThanOrEqual(15)
    expect(sponsorSide.filter((f) => /StudentTabBar/.test(f.code)).map((f) => f.rel)).toEqual([])
    // The landing keeps the student header (signed-out visitors), with its tabs turned off.
    expect(readWeb('src/components/SponsorLanding.tsx', 'the sponsor landing')).toContain('<AppHeader tabs={false} />')
  })
  test('it is the student bar\'s CSS with three columns; the giving statement prints without it', () => {
    const bar = readWeb('src/components/sponsor/SponsorTabBar.tsx', 'the sponsor tab bar')
    expect(bar).toMatch(/<nav data-tab-bar="sponsor"/)
    expect((bar.match(/href: '\/sponsor[^']*'/g) ?? []).length).toBe(3)
    const css = readWeb('src/app/globals.css', 'the stylesheet').replace(/\/\*[\s\S]*?\*\//g, '')
    expect(css).toMatch(/\[data-tab-bar='sponsor'\] \{\s*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);/)
    expect(css).toMatch(/@media print \{[\s\S]*\[data-tab-bar\] \{\s*display: none !important;/)
    // M5 review: without :has() the sponsor's phone header is the logo alone, so the bar is the only way to
    // My Account and Log out — there it is drawn in the flow (never fixed: it could not give way to a page bar).
    const fallback = css.slice(css.indexOf('@supports not selector(:has(*))'))
    expect(css).toContain('@supports not selector(:has(*))')
    expect(fallback).toMatch(/^@supports not selector\(:has\(\*\)\) \{\s*@media \(max-width: 767\.98px\) \{\s*\[data-tab-bar='sponsor'\] \{\s*display: grid;\s*position: static;/)
  })
  test('every bar pinned to the foot of a sponsor screen carries data-page-bar', () => {
    const bars: string[] = []
    const offenders: Offender[] = []
    for (const f of TSX.filter((x) => SPONSOR_SCOPE(x.rel))) {
      for (const name of ['div', 'nav', 'footer', 'section', 'form', 'aside', 'header']) {
        for (const tag of openTags(f.code, name)) {
          if (!PINNED_BOTTOM(classText(f, tag, resolve))) continue
          bars.push(f.rel)
          if (!/(^|\s)data-page-bar(\s|=|$)/.test(tag.attrs)) offenders.push(where(f, tag.start, tag.attrs))
        }
      }
    }
    // M5: the fund bar (one pool student) and the terms quiz's bar.
    expect(bars.length).toBeGreaterThanOrEqual(2)
    // M5 review (consent): "Start the quiz" is INLINE after the terms and the privacy line, never pinned.
    const wizard = readWeb('src/components/sponsors/SponsorTermsWizard.tsx', 'the terms wizard')
    const at = wizard.indexOf('data-testid="terms-start"')
    const start = at < 0 ? '' : wizard.slice(wizard.lastIndexOf('<button', at), wizard.indexOf('</button>', at))
    expect(start).not.toBe('')
    expect(start).not.toMatch(/\bsticky\b|\bfixed\b/)
    expect(wizard.indexOf("t('sponsorPortal.terms.privacyNote')")).toBeLessThan(wizard.indexOf('data-testid="terms-start"'))
    expect(wizard.slice(wizard.indexOf("{phase === 'read'"), wizard.indexOf("{phase === 'quiz'"))).not.toContain('data-page-bar')
    expect(offenders).toEqual([])
  })
  test('a Sheet on a portal screen keeps the portal face (it is portalled out of the shell)', () => {
    const portal = FILES.filter((f) => /^src\/(app\/sponsor\/\(portal\)|components\/sponsor)\//.test(f.rel))
    const sheets = portal.flatMap((f) => openTags(f.code, 'Sheet').map((tag) => ({ f, tag })))
    expect(sheets.length).toBeGreaterThanOrEqual(2)   // the fund confirm and the filter Sheet
    expect(sheets.filter(({ tag }) => !/className="[^"]*\bfont-sponsor\b/.test(tag.attrs)).map(({ f, tag }) => where(f, tag.start, tag.attrs))).toEqual([])
    const css = readWeb('src/app/globals.css', 'the stylesheet')
    expect(css).toMatch(/\.font-sponsor \{\s*font-family: var\(--font-tamil\), var\(--font-inter\), system-ui, sans-serif;/)
  })
  test('a synthetic sponsor identity is supplied by the sandbox only', () => {
    // Product code provides it in ONE place — the real provider, which reads the Supabase session.
    const providers = FILES.filter((f) => /SponsorAuthContext\.Provider/.test(f.code)).map((f) => f.rel)
    expect(providers).toEqual(['src/lib/sponsor-auth-context.tsx'])
    expect(readWeb('src/lib/sponsor-auth-context.tsx', 'the sponsor auth context')).toMatch(/export function SponsorAuthProvider[\s\S]*getSponsorSession\(\)/)
  })
})

// ── Rule 11: the console shell on a phone (Mobile M6a) ─────────────────────────────────────────────
/**
 * The console's phone bar is ONE pinned row of 44 px controls — Menu · where you are · Search ·
 * Notifications · Account — and everything the bar holds from `md` that is not in that row (the theme,
 * Help) is in the phone menu, with Guide, FAQ, Profile and Log out. The phone menu's Log out is the account
 * menu's Log out: both are the ONE `signOut` in AppShell, whose body is pinned here word for word.
 */
describe('rule 11 — the console shell on a phone', () => {
  const topbar = () => readWeb('src/components/admin/Topbar.tsx', 'the console top bar')
  const shell = () => readWeb('src/components/admin/AppShell.tsx', 'the console shell')
  test('the phone row is pinned, and each control in it is 44 x 44', () => {
    const src = topbar()
    const header = (src.match(/<header data-admin-topbar className="([^"]+)"/) ?? [])[1] ?? ''
    expect(header.split(' ')).toEqual(expect.arrayContaining(['max-md:sticky', 'max-md:top-0', 'max-md:min-h-14']))
    expect(header).toMatch(/max-md:pt-\[max\([^)]*env\(safe-area-inset-top\)\)\]/)
    // Menu and Search are 44 x 44 on a phone; Notifications and Account are Menu triggers (below).
    expect(src).toMatch(/aria-label=\{t\('common\.menu'\)\}\s*className="inline-flex h-11 w-11 /)
    expect(src).toMatch(/aria-label=\{t\('admin\.shell\.search'\)\}\s*className="[^"]*max-md:h-11 max-md:w-11/)
    const menu = readWeb('src/components/admin/Menu.tsx', 'the console menu')
    expect(menu).toMatch(/aria-controls[\s\S]*?className="[^"]*max-md:min-h-11 max-md:min-w-11/)
    expect(menu).toMatch(/const cls = `[^`]*max-md:min-h-11/)
  })
  test('the theme and Help leave the phone row — and are in the phone menu instead', () => {
    const src = topbar()
    expect(src).toContain('<div className="hidden md:block"><ThemeSelector /></div>')
    expect(src).toMatch(/<div className="hidden md:block"><Menu label=\{t\('admin\.shell\.help'\)\}/)
    // The phone names where you are as TEXT; the switchers are not squeezed into the row.
    expect(src).toMatch(/<nav aria-label="Breadcrumb" className="hidden [^"]*md:flex"/)
    const drawer = shell().slice(shell().indexOf('data-admin-drawer'))
    for (const piece of ['<ThemeSegments />', "t('admin.guideNav')", "t('admin.faqNav')", "t('admin.profile')",
      "t('header.logout')", '{scopeSwitchers}', "aria-label={t('common.dismiss')}"]) {
      expect(drawer).toContain(piece)
    }
  })
  test('ONE sign-out, two doors: the body is exactly the account menu\'s, and both doors call it', () => {
    const src = shell()
    expect(src).toContain("const signOut = async () => { await adminSignOut(); router.replace('/admin/login') }")
    // Nothing else signs out: one call of adminSignOut in the shell, inside that line.
    expect((src.match(/adminSignOut\(/g) ?? []).length).toBe(1)
    expect(src).toContain('onSignOut={signOut}')
    const drawer = src.slice(src.indexOf('data-admin-drawer'))
    expect(drawer).toMatch(/<button type="button" onClick=\{signOut\}/)
    const bar = topbar()
    expect(bar).toMatch(/<MenuItem icon=\{<Icon name="signOut" \/>\} danger onClick=\{onSignOut\}>/)
  })
  test('the phone menu rows are 44 px (the rail keeps its 32 px from lg)', () => {
    const src = readWeb('src/components/admin/Sidebar.tsx', 'the console sidebar')
    expect(src).toMatch(/group\/row relative flex h-11 [^`]*lg:h-8/)
    expect(src).toMatch(/flex h-11 cursor-default [^"]*lg:h-8/)
  })
  test('the case list on a phone: whole-row links, no tooltip, filters in the Sheet, one set of controls', () => {
    const src = readWeb('src/app/admin/scholarship/page.tsx', 'the case list')
    const phone = src.slice(src.indexOf('data-testid="application-cards"'), src.indexOf('<TableFrame'))
    expect(phone).not.toBe('')
    expect(phone).not.toMatch(/\btitle=/)
    expect(phone).toMatch(/<Link href=\{`\/admin\/scholarship\/\$\{a\.id\}`\} data-row-link/)
    expect(phone).not.toMatch(/text-\[(9|10|11)px\]/)
    // ONE set of filters: the desktop row draws it, and the phone tools get the same nodes for their Sheet.
    expect(src).toContain('<div className="hidden md:contents">{filterControls}</div>')
    expect(src).toMatch(/<CaseListPhoneTools filters=\{filterControls\}/)
    const tools = readWeb('src/components/admin/CaseListPhoneTools.tsx', 'the case list phone tools')
    expect(tools).toMatch(/<Sheet open=\{open\}[\s\S]*data-testid="list-filter-sheet">\s*\{filters\}/)
    expect(tools).not.toMatch(/useState\(['"]/)   // it owns no filter value of its own
    expect(src.slice(src.indexOf('const filterControls'), src.indexOf('const activeFilters'))).not.toMatch(/\btitle=/)
  })
})

// ── The cockpit on a phone (Mobile M6b) ────────────────────────────────────────────────────────────
/**
 * Owner, 2026-11-03: the decision bar JUMPS and never saves; a PDF opens in the phone's own viewer; scheduling a
 * tranche and the payment actions are read-only on a phone. And rule 9 / 15: no scroll box inside the page.
 */
describe('the cockpit on a phone', () => {
  const VIEW = 'src/app/admin/scholarship/[id]/view'
  test('payments are read-only on a phone: every money control sits in a below-md-hidden container', () => {
    const src = readWeb(`${VIEW}/PostAwardPanels.tsx`, 'the post-award panels')
    const box = (marker: string) => {
      const at = src.indexOf(marker)
      const open = src.lastIndexOf('<div', at)
      return { tag: src.slice(open, src.indexOf('>', at) + 1), body: src.slice(at, src.indexOf('</div>', src.indexOf('</button>', at))) }
    }
    const actions = box('data-payment-actions')
    expect(actions.tag).toMatch(/className="[^"]*\bmax-md:hidden\b/)
    expect(actions.body).toContain('doDisbursementAction(d.id, action)')
    const schedule = box('data-schedule-tranche')
    expect(schedule.tag).toMatch(/className="[^"]*\bmax-md:hidden\b/)
    expect(schedule.body).toContain('onClick={doScheduleTranche}')
    // Nowhere else: one door each, and both inside those boxes.
    expect((src.match(/doDisbursementAction\(/g) ?? []).length).toBe(1)
    expect((src.match(/onClick=\{doScheduleTranche\}/g) ?? []).length).toBe(1)
    expect(src).toMatch(/<p className="[^"]*\bmd:hidden\b[^"]*" data-payments-use-computer>\s*\{t\('admin\.disbursement\.useComputer'\)\}/)
  })
  test('the documents list scrolls in the page on a phone (its own scroll box is md: only)', () => {
    const src = readWeb(`${VIEW}/DocumentsDrawer.tsx`, 'the documents drawer')
    const list = (src.match(/<div className="([^"]*)" data-docs-list>/) ?? [])[1] ?? ''
    expect(list.split(' ')).toEqual(expect.arrayContaining(['md:max-h-[28rem]', 'md:overflow-y-auto']))
    expect(list.split(' ').filter((c) => /^(max-h-|overflow-y-)/.test(c))).toEqual([])
  })
  test('a PDF on a phone is an Open link to a new tab, never an iframe', () => {
    const src = readWeb('src/components/DocViewer.tsx', 'the document viewer')
    const code = src.split('\n').filter((l) => !/^\s*(\/\/|\*|\/\*\*)/.test(l)).join('\n')
    expect((code.match(/<iframe\b/g) ?? []).length).toBe(1)
    expect(src).toMatch(/\{doc\.kind === 'pdf' && !phone && \(\s*<iframe/)
    expect(src).toMatch(/\{doc\.kind === 'pdf' && phone && \([\s\S]*?<a href=\{doc\.url\} target="_blank" rel="noreferrer"\s*className="[^"]*\bmin-h-12\b/)
  })
  test('the decision bar jumps and never decides: no request, no outcome, no Save', () => {
    const src = readWeb(`${VIEW}/DecisionBar.tsx`, 'the decision bar')
    const code = src.split('\n').filter((l) => !/^\s*(\/\/|\*|\/\*\*)/.test(l)).join('\n')
    expect(code).toMatch(/<div data-page-bar data-decision-bar\s+className="[^"]*\bsticky bottom-0\b[^"]*\bmd:hidden"/)
    expect(code).not.toMatch(/^import (?!type )[^\n]*from '@\/lib\/admin-api'/m)   // types only: it can call nothing
    expect(code).toMatch(/import type \{ AdminScholarshipDetail \} from '@\/lib\/admin-api'/)
    expect(code).not.toMatch(/\bdo[A-Z]\w*\b|\bfetch\(|setOfficerVerdict|recordVerdict\(/)
    expect((code.match(/onClick=/g) ?? []).length).toBe(1)
    expect(code).toMatch(/onClick=\{\(\) => document\.getElementById\('decision-section'\)\?\.scrollIntoView\(/)
    const view = readWeb('src/app/admin/scholarship/[id]/view.tsx', 'the cockpit view')
    // "Ready" only when nothing is in flight (M6b review).
    expect(view).toMatch(/decisionBarShows\(\{ app, decisionReopened, decisionRecorded, decisionLocked, canWrite \}\) && \(\s*<DecisionBar t=\{t\} outcome=\{officerVerdict\.overall\} canSave=\{canSave && !busy\} \/>/)
    // ONE rule (M6b review): the card gates its Save controls on the same helper the bar shows on.
    const card = readWeb('src/app/admin/scholarship/[id]/view/DecisionCard.tsx', 'the decision card')
    expect(card).toContain('const saveShows = decisionBarShows({ app, decisionReopened, decisionRecorded, decisionLocked, canWrite })')
    expect(card).toMatch(/\? \(\s*(?:\/\/[^\n]*\n\s*)*saveShows && \(/)
    expect(card).not.toMatch(/\.includes\(app\.status\)\) \? \(\s*canWrite && \(/)
  })
})

// ── Rule 5: one shared Sheet, no hand-rolled overlays ─────────────────────────────────────────
/**
 * Every hand-rolled `fixed inset-0` overlay re-decided max height, inner scroll, the close target
 * and the safe area — and several decided wrong (buttons hidden behind the iPhone keyboard). Since
 * Mobile M1b the shared `Sheet` (src/components/Sheet.tsx) is the ONE home of an overlay. The 18
 * that existed moved onto it in M1b part 2, except the three below, which are not dialogs and say
 * why. This is now a POSITIVE guard, not a floor: a `fixed inset-0` anywhere else FAILS — use Sheet.
 * Counted per class string holding both tokens, in `.ts` and `.tsx`.
 */
const OVERLAY_HOMES: string[] = ['src/components/Sheet.tsx']

/** Full-screen panels that are NOT dialogs. Each was made phone-correct in M1b and says why it stays. */
const OVERLAY_EXEMPT: Record<string, string> = {
  'src/components/DocViewer.tsx':
    'a document viewer needs the whole screen (full screen on a phone, framed on a desktop), not a '
    + 'bottom sheet capped at 90 % — dvh, notch padding and a 44 px close since M1b',
  'src/components/admin/AppShell.tsx':
    'the console’s phone navigation drawer, sliding from the left edge — a side panel, not a '
    + 'dialog; safe-area padded (M1a) and closed by Escape, the backdrop or a choice',
  'src/components/admin/CommandPalette.tsx':
    'a type-to-search command palette reached by Ctrl/⌘-K: the box sits at the top so results grow '
    + 'DOWN under it while typing (a bottom sheet would hide them behind the keyboard); its own '
    + 'tested focus, arrow-key and Escape handling',
}

describe('rule 5 — overlays come from the shared Sheet', () => {
  test('the home and every exemption are real files that really hold an overlay', () => {
    // An exemption for a file that no longer holds the overlay would excuse nothing and hide a move.
    for (const rel of [...OVERLAY_HOMES, ...Object.keys(OVERLAY_EXEMPT)]) {
      const f = FILES.find((x) => x.rel === rel)
      expect(`${rel}: ${!!f && /fixed inset-0/.test(f.code)}`).toBe(`${rel}: true`)
    }
  })

  test('no fixed inset-0 overlay outside Sheet.tsx and the named exemptions', () => {
    // Mobile M1b part 2: was a floor of 18; now none may be added. A new overlay uses Sheet.
    const offenders = FILES
      .filter((f) => !OVERLAY_HOMES.includes(f.rel) && !(f.rel in OVERLAY_EXEMPT))
      .flatMap((f) => literalsWithIndex(f.code)
        .filter(({ text }) => tokens(text).includes('fixed') && tokens(text).includes('inset-0'))
        .map(({ index }) => where(f, index, 'fixed inset-0')))
    expect(offenders).toEqual([])
  })
})

// ── Rule 6: dvh, never vh ─────────────────────────────────────────────────────────────────────
/**
 * On iPhone `100vh` is the height with the address bar HIDDEN, so a `vh` box is taller than the
 * screen while the bar shows and its bottom (often the main button) sits off-screen. `dvh` follows
 * the bar. Counted: a height utility with a `vh` value (`h-[70vh]`, `max-h-[90vh]`, `min-h-[80vh]`),
 * `h-screen` and `max-h-screen`, and a bare `NNvh` / `calc(…vh…)` string (an inline style). A `vh`
 * PADDING or offset (`pt-[12vh]`) is not counted: it moves a box a little, it does not make one
 * taller than the visible screen, which is the bug.
 *
 * `min-h-screen` is counted SEPARATELY, with its own floor: as a minimum it only makes a page at
 * least a screen tall, which is mostly harmless (the page scrolls), but it still over-measures on
 * iPhone and belongs on `min-h-dvh` in time.
 */
const VH_TOKEN = /^(?:[\w-]+:)*(?:(?:h|max-h)-screen|(?:h|min-h|max-h)-\[[^\]]*\dvh[^\]]*\])$/
const VH_STYLE = /^(?:\d*\.?\d+vh|calc\(.*\dvh.*\))$/
const MIN_SCREEN = /^(?:[\w-]+:)*min-h-screen$/

describe('rule 6 — heights use dvh, never vh', () => {
  test('vh heights: at or under the floor', () => {
    const offenders = FILES.flatMap((f) => literalsWithIndex(f.code).flatMap(({ text, index }) => {
      // A style VALUE is matched whole (`calc(100vh - 4rem)` has spaces); class tokens one by one.
      const style = text.trim()
      const hits = [
        ...tokens(text).filter((t) => VH_TOKEN.test(t)),
        ...(VH_STYLE.test(style) ? [style] : tokens(text).filter((t) => VH_STYLE.test(t))),
      ]
      return hits.map((t) => where(f, index, t))
    }))
    // Mobile M1b part 2: 3 -> 1. AuthGateModal's max-h-[90vh] went with its shell (Sheet), and
    // DocViewer's 92vh is 92dvh; the one left is the contracts template preview (desktop-only).
    ratchet('vh-based heights', offenders, 1)
  })

  test('min-h-screen: at or under its own floor', () => {
    const offenders = FILES.flatMap((f) => literalsWithIndex(f.code).flatMap(({ text, index }) =>
      tokens(text).filter((t) => MIN_SCREEN.test(t)).map((t) => where(f, index, t))))
    // 71 → 69 (Mobile M3): the report page's loading and error states became `min-h-[60dvh]` under its header.
    ratchet('min-h-screen', offenders, 69)
  })
})

// ── Rule 4: no hover-only explanation on an icon-only control ─────────────────────────────────
/**
 * A phone has no hover, so a `title=` tooltip is never seen there. On a control with words it is
 * a spare; on an ICON-ONLY control it is the only explanation, and the tap target is a mystery.
 * Counted: `<button>`, `<a>` and `<Link>` that carry `title=` and whose content has no words.
 *
 * ⚠ BEST EFFORT, AND WHICH WAY IT LEANS. "No words" means: once `<svg>…</svg>` and every tag are
 * removed, no letters or digits remain, and every `{…}` left holds JSX (an icon) rather than a
 * value. An expression the reader cannot judge (`{label}`) is taken to be words — so this UNDER-
 * counts rather than over-counts. `role="button"` elements and custom components are not seen.
 */
/** The element's content; null when the reader cannot find its closing tag — an UNKNOWN, which
 *  is never counted as an offender (it would be a guess, and a guess must not fail a build). */
function contentOf(code: string, tag: { name: string; end: number; selfClosing: boolean }): string | null {
  if (tag.selfClosing) return ''
  const close = code.indexOf(`</${tag.name}>`, tag.end)
  return close === -1 ? null : code.slice(tag.end + 1, close)
}

function isIconOnly(content: string): boolean {
  const noSvg = content.replace(/<svg[\s\S]*?<\/svg>/g, ' ')
  const exprs: string[] = []
  // Pull out top-level `{…}` expressions, then strip tags from what is left.
  let rest = ''
  let depth = 0
  let cur = ''
  for (const c of noSvg) {
    if (c === '{') { if (depth === 0) cur = ''; else cur += c; depth++; continue }
    if (c === '}') { depth--; if (depth === 0) exprs.push(cur); else cur += c; continue }
    if (depth > 0) cur += c
    else rest += c
  }
  const text = rest.replace(/<[^>]*>/g, ' ').replace(/&[a-z]+;|&#\d+;/g, ' ')
  if (/[\p{L}\p{N}]/u.test(text)) return false
  return exprs.every((e) => !e.trim() || (/</.test(e) && !/'[^']*'|"[^"]*"|\bt\(/.test(e)))
}

/**
 * Files that serve ONLY desktop-only routes (`mobileClass.ts`, class `desktop`). Below `md` those
 * routes show the "works best on a computer" panel (rule 13), so a phone never reaches these
 * controls and a hover hint there is acceptable. Each entry names its route; a stale one fails below.
 */
const DESKTOP_ONLY_FILES: Record<string, string> = {
  'src/components/contracts/ClauseEditor.tsx':
    "the clause editor's icon toolbar (insert, indent, move, remove) — only on /admin/contracts/[id]",
}

describe('rule 4 — no title= as the only explanation on an icon-only control', () => {
  test('a desktop-only exemption names a real file used only by a desktop route', () => {
    for (const rel of Object.keys(DESKTOP_ONLY_FILES)) {
      expect(`${rel}: ${FILES.some((f) => f.rel === rel)}`).toBe(`${rel}: true`)
    }
    expect(MOBILE_CLASS['/admin/contracts/[id]'].cls).toBe('desktop')
  })

  test('icon-only controls explained only by title=: at or under the floor', () => {
    const offenders = TSX.filter((f) => !(f.rel in DESKTOP_ONLY_FILES)).flatMap((f) => ['button', 'a', 'Link'].flatMap((name) =>
      openTags(f.code, name)
        .filter((tag) => /(?:^|\s)title=/.test(tag.attrs))
        .filter((tag) => {
          const content = contentOf(f.code, tag)
          return content !== null && isIconOnly(content)
        })
        .map((tag) => where(f, tag.start, `<${name} title=… (icon only)`))))
    // Mobile M1a: 7 -> 0. Six were ClauseEditor's toolbar, now exempt above (desktop-only route);
    // the seventh, the course-interest remove button, has an aria-label and a 44 px target.
    // VerifiedTick (a role="img" span, which this rule never counted) is tappable too since M1a.
    ratchet('icon-only controls with title=', offenders, 0)
  })
})

// ── The viewport: safe areas on, zoom never off ───────────────────────────────────────────────
describe('the root layout sets the phone viewport', () => {
  const layout = readWeb('src/app/layout.tsx',
    'the viewport export lives in the root layout; Next only reads it from a layout or page')
  const block = (layout.match(/export const viewport[^=]*=\s*\{([\s\S]*?)\n\}/) ?? ['', ''])[1]

  test('exports `viewport` with viewportFit cover, so env(safe-area-inset-*) works', () => {
    expect(block).not.toBe('')
    expect(block).toMatch(/viewportFit:\s*'cover'/)
    expect(block).toMatch(/width:\s*'device-width'/)
    expect(block).toMatch(/initialScale:\s*1\b/)
  })

  test('never blocks zoom — a person who needs bigger text must be able to pinch', () => {
    expect(block).not.toMatch(/maximumScale|userScalable/)
  })

  test('the browser-bar colours are the header’s own token, --ground-0, in each mode', () => {
    // A hex here would fail the theme guard; an `rgb()` that drifted from the token would not, so
    // the two are compared. Light is the `:root` block, dark the `[data-theme='dark']` block.
    const css = readWeb('src/app/globals.css', 'the colour tokens the theme colour must equal')
    const dark = css.indexOf("[data-theme='dark']")
    const token = (from: number) => (css.slice(from).match(/--ground-0:\s*([\d ]+);/) ?? ['', ''])[1].trim()
    expect(block).toContain(`'(prefers-color-scheme: light)', color: 'rgb(${token(0)})'`)
    expect(block).toContain(`'(prefers-color-scheme: dark)', color: 'rgb(${token(dark)})'`)
  })
})

// ── The home-screen app: a manifest and real icons, nothing more ──────────────────────────────
describe('HalaTuju installs as a home-screen app', () => {
  /** A PNG's width and height, from its IHDR chunk (bytes 16–23). */
  const pngSize = (rel: string): string => {
    const buf = fs.readFileSync(path.join(WEB_ROOT, ...rel.split('/')))
    return `${buf.readUInt32BE(16)}x${buf.readUInt32BE(20)}`
  }
  const manifest = readWeb('src/app/manifest.ts', 'Next serves the web app manifest from this file')

  // 'browser' until M8: an iPhone standalone app has no back button and storage apart from Safari,
  // so a sign-in link would land in Safari and the app would never see it (see manifest.ts).
  test('the manifest opens in the browser, not standalone, at the home page', () => {
    expect(manifest).toMatch(/display:\s*'browser'/)
    expect(manifest).toMatch(/start_url:\s*'\/'/)
  })

  test('every icon the manifest names is on disk, at the size it claims', () => {
    const icons = Array.from(manifest.matchAll(/src:\s*'([^']+)',\s*sizes:\s*'([^']+)'/g), (m) => [m[1], m[2]])
    expect(icons.length).toBeGreaterThanOrEqual(3)
    expect(manifest).toMatch(/purpose:\s*'maskable'/)
    for (const [src, sizes] of icons) expect(`${src} ${pngSize(`public${src}`)}`).toBe(`${src} ${sizes}`)
  })

  test('the iPhone home-screen icon is 180 px', () => {
    expect(pngSize('src/app/apple-icon.png')).toBe('180x180')
  })

  test('no service worker — an installed HalaTuju is the live site, never a stale copy', () => {
    const sw = FILES.filter((f) => /serviceWorker\.register|navigator\.serviceWorker/.test(f.code))
    expect(sw.map((f) => f.rel)).toEqual([])
  })
})

// ── Every route is classed (the ledger's source) ──────────────────────────────────────────────
/**
 * ⚠ A CLOSED SET, ON PURPOSE. `src/lib/mobileClass.ts` must name every `page.tsx` route and nothing
 * else. One extra file IS the defect here: a new page with no class has had nobody decide whether
 * a phone may see it, and a stale entry keeps a ledger row for a screen that no longer exists.
 * `page.sandbox.tsx` is not a route in production and is not classed.
 */
describe('every route has a phone class', () => {
  const APP = path.join(WEB_ROOT, 'src', 'app')
  const pages = walkFloor(APP, 90, 'every page.tsx is a route that must carry a phone class; 93 '
    + 'routes on 2026-10-31', { exts: ['page.tsx'] })
    .filter((full) => path.basename(full) === 'page.tsx')
    .map((full) => routeOfPage(path.relative(APP, full).split(path.sep).join('/')))
    .sort()

  test('the classification and the pages on disk are the same set', () => {
    const classed = Object.keys(MOBILE_CLASS).sort()
    expect({ unclassed: pages.filter((r) => !(r in MOBILE_CLASS)),
      stale: classed.filter((r) => !pages.includes(r)) })
      .toEqual({ unclassed: [], stale: [] })
  })

  test('every desktop-only route says why, in words', () => {
    for (const [route, e] of Object.entries(MOBILE_CLASS)) {
      if (e.cls === 'desktop') expect(`${route}: ${e.why.trim().length > 20}`).toBe(`${route}: true`)
    }
  })

  test('a redirect names a route that exists, and a surface names a real sandbox slug', () => {
    // The SAME reader the browser check uses (SURFACES block only, one `render:` per slug), so the
    // ledger and the check cannot disagree about which surfaces exist.
    const slugs = sandboxSlugs()
    expect(slugs.length).toBeGreaterThanOrEqual(15)
    for (const [route, e] of Object.entries(MOBILE_CLASS)) {
      if (e.redirect) expect(`${route} → ${pages.includes(e.redirect.split('?')[0])}`).toBe(`${route} → true`)
      for (const s of e.surfaces ?? []) expect(`${route} → ${s}: ${slugs.includes(s)}`).toBe(`${route} → ${s}: true`)
    }
  })
})

// ── The reader itself (M0 review) ─────────────────────────────────────────────────────────────
/**
 * Each case below is a shape the first reader got WRONG, found by the M0 code review. They pin the
 * reader, not the product: if one fails, a floor above has silently started counting something else.
 */
describe('the reader sees what the review said it missed', () => {
  const scanned = (rel: string, raw: string): Scanned => ({ rel, raw, code: blankComments(raw) })

  test('a URL or a `//` in JSX text is not a comment; a real comment still is', () => {
    expect(blankComments("<a href={u}>https://halatuju.example/x className='text-sm'</a>"))
      .toContain("className='text-sm'")
    expect(blankComments('<p>a // b</p>')).toContain('// b')
    expect(blankComments("const x = 1 // className='text-sm'")).not.toContain('text-sm')
  })

  test('an aliased import resolves by the name it was EXPORTED under', () => {
    const lib = scanned('src/x/fields.ts', "export const INPUT = 'w-full text-sm'")
    const page = scanned('src/x/page.tsx', "import { INPUT as fieldCls } from './fields'\n"
      + '<input className={fieldCls} />')
    const tag = openTags(page.code, 'input')[0]
    expect(classText(page, tag, constResolver([lib, page]))).toContain('text-sm')
  })

  test('a constant inside a template hole is resolved', () => {
    expect(withoutLiterals('`${inputCls} w-full`')).toContain('inputCls')
    const page = scanned('src/x/p.tsx', "const inputCls = 'text-xs'\n<input className={`${inputCls} w-28`} />")
    expect(classText(page, openTags(page.code, 'input')[0], constResolver([page]))).toContain('text-xs')
  })

  test('a small size counts when it applies on a phone, and only then', () => {
    for (const t of ['text-sm', 'max-md:text-sm', 'max-sm:text-xs', '!text-sm', 'focus:text-sm',
      'text-[length:14px]', 'text-[13.5px]', 'text-sm/6', 'max-[500px]:text-xs']) {
      expect(`${t}: ${smallOnPhone(t)}`).toBe(`${t}: true`)
    }
    for (const t of ['md:text-sm', 'sm:text-xs', 'lg:!text-sm', 'min-[640px]:text-sm',
      'placeholder:text-sm', 'text-base', 'text-[16px]', 'text-[1rem]', 'md:max-lg:text-sm']) {
      expect(`${t}: ${smallOnPhone(t)}`).toBe(`${t}: false`)
    }
  })

  test('a vh style value is matched whole, spaces and all', () => {
    expect(VH_STYLE.test('calc(100vh - 4rem)')).toBe(true)
    expect(VH_STYLE.test('100vh')).toBe(true)
    expect(VH_STYLE.test('calc(100dvh - 4rem)')).toBe(false)
  })
})
