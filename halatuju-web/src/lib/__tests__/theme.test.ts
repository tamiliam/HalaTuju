/**
 * The theme mechanism, and the two guards the owner's rulings depend on (Layer 1 F1).
 *
 * These are structural tests. What dark mode LOOKS like is a browser question and is reviewed on the
 * sandbox — a passing test here says the machinery is right, never that the result is good.
 */
import fs from 'fs'
import path from 'path'
import {
  DEFAULT_MODE, THEME_ATTR, THEME_MODES, THEME_STORAGE_KEY, isThemeMode, resolveTheme,
} from '../theme'
import { PLATFORM, brandRamp } from '../branding'

const read = (p: string) => fs.readFileSync(path.join(process.cwd(), p), 'utf8')

/**
 * Every way a raw Tailwind colour can be spelled. Shared by the per-surface conversion guards
 * below — ONE copy, because two copies drift and the second one silently stops catching things.
 */
const RAW = /\b(?:bg|text|border|ring|divide|from|to|via|placeholder|fill|stroke|outline|shadow|accent|decoration|caret)-(?:gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/

/**
 * Google's own four brand hexes, in the sign-in button's logo. A third-party mark must NOT follow
 * our theme — recolouring someone else's logo is a misuse of it. This is the ONLY hex allowlist.
 */
const GOOGLE_LOGO = new Set(['#4285F4', '#34A853', '#FBBC05', '#EA4335'])

/**
 * HTML numeric entities removed, before any hex scan. `&#128100;` is 👤 and `&#127973;` is 🏥 —
 * both read as "#" followed by valid hex digits, so a colour scan reports them as raw hex. F4's
 * admin pages use a dozen as section icons. An entity is markup, not a colour.
 */
const withoutEntities = (s: string) => s.replace(/&#\d+;/g, ' ')

/**
 * Comments removed, for the hex scan only.
 *
 * ⚠ WITHOUT THIS THE GUARD FLAGS ITS OWN DOCUMENTATION. `#15a` and `#15b` are audit references in
 * `ActionCentre`'s comments and are three valid hex digits; the note explaining why `VerifiedTick`
 * no longer carries `#fff` contains the very string it is there to forbid. A guard that reads
 * source text has to know the difference between code and prose, or the only way to pass it is to
 * stop writing comments — which is the opposite of what it is for.
 */
const withoutComments = (s: string) => s
  .replace(/\/\*[\s\S]*?\*\//g, ' ')        // /* … */ and JSX {/* … */}
  .replace(/(^|[^:])\/\/[^\n]*/g, '$1')     // // … , but not the // in https://

/** Every `.ts`/`.tsx` under `dir`, tests excluded. */
const walkFiles = (dir: string, into: string[] = []): string[] => {
  for (const e of fs.readdirSync(path.join(process.cwd(), dir), { withFileTypes: true })) {
    if (e.name === '__tests__') continue
    const rel = path.join(dir, e.name)
    if (e.isDirectory()) walkFiles(rel, into)
    else if (/\.tsx?$/.test(e.name) && !/\.test\./.test(e.name)) into.push(rel)
  }
  return into
}

/**
 * The three assertions that say a surface is CONVERTED. Applied per surface as each repaint sprint
 * lands one, so a surface already migrated cannot have raw colour creep back into it — Tailwind's
 * own `gray`/`blue`/… stay available for the surfaces not yet done, so the absence of the utility
 * can never be the guard.
 */
function assertConverted(name: string, files: string[], minFiles: number) {
  describe(`${name} is fully converted`, () => {
    it('mounts enough files for this test to mean something', () => {
      expect(files.length).toBeGreaterThanOrEqual(minFiles)
    })

    it('has no raw Tailwind colour left anywhere in it', () => {
      const offenders = files
        .map((f) => [f, read(f).match(new RegExp(RAW, 'g'))] as const)
        .filter(([, m]) => m)
        .map(([f, m]) => `${f}: ${Array.from(new Set(m!)).join(', ')}`)
      expect(offenders).toEqual([])
    })

    it('has no raw hex colour either — the half a class scan cannot see', () => {
      // Found in the F1 browser pass: the giving donut is a conic-gradient, which cannot be a
      // utility, so it carried its three colours in an inline style and stayed a light-mode island
      // in dark. F2a found the same shape again — `VerifiedTick`'s tick was `stroke="#fff"`.
      // Colour hides in inline styles, SVG fills and lib constants.
      const offenders: string[] = []
      for (const f of files) {
        for (const hex of withoutEntities(withoutComments(read(f))).match(/#[0-9a-fA-F]{3,8}\b/g) ?? []) {
          if (!GOOGLE_LOGO.has(hex.toUpperCase())) offenders.push(`${f}: ${hex}`)
        }
      }
      expect(offenders).toEqual([])
    })

    it('keeps white literal — it must NOT invert with the ground', () => {
      // 214 uses across the product, nearly all on a coloured or dark surface: a button label, a
      // filled badge, the tick inside a seal. Mapped onto --ground-0 they turn black in dark mode.
      // The codemod converts BACKGROUND white only; this asserts the distinction survived here.
      const withWhite = files.filter((f) => /\b(?:text|stroke|border|ring)-white\b/.test(read(f)))
      expect(withWhite.length).toBeGreaterThan(0)
      for (const f of withWhite) expect(read(f)).not.toMatch(/\b(?:text|stroke)-ground-0\b/)
    })
  })
}

describe('resolveTheme', () => {
  it('honours an explicit choice regardless of what the device wants', () => {
    // A person who has said "dark" has said it. `prefers-color-scheme` is the initial default,
    // never an override of an explicit choice.
    expect(resolveTheme('dark', false)).toBe('dark')
    expect(resolveTheme('light', true)).toBe('light')
  })

  it('follows the device on auto — in both directions', () => {
    expect(resolveTheme('auto', true)).toBe('dark')
    expect(resolveTheme('auto', false)).toBe('light')
  })

  it('defaults to auto, so a new person inherits their own machine', () => {
    expect(DEFAULT_MODE).toBe('auto')
  })

  it('rejects anything that is not a mode', () => {
    expect(THEME_MODES).toEqual(['light', 'dark', 'auto'])
    for (const bad of ['', 'DARK', 'system', null, undefined, 0]) {
      expect(isThemeMode(bad)).toBe(false)
    }
  })
})

describe('the before-paint boot script', () => {
  // It cannot import the module — a blocking head script has no module system — so the key, the
  // attribute and the default are written twice. This is the test that stops the copy drifting.
  const boot = read('public/theme-boot.js')

  it('reads the same storage key the module writes', () => {
    expect(boot).toContain(`'${THEME_STORAGE_KEY}'`)
  })

  it('sets the same attribute globals.css keys the dark ramp off', () => {
    expect(boot).toContain(`'${THEME_ATTR}'`)
    expect(read('src/app/globals.css')).toContain(`[${THEME_ATTR}='dark']`)
  })

  it('falls back to the same default as the module', () => {
    expect(boot).toContain(`mode = '${DEFAULT_MODE}'`)
  })

  it('survives storage being unavailable rather than throwing', () => {
    // Private-mode Safari throws on READ, not only on write. A theme is never worth an exception
    // in a script that blocks the first paint of every page.
    expect(boot).toContain('catch')
  })

  it('IS GATED ON THE FLAG — with the switch off, nothing paints a theme at all', () => {
    // ⚠ THE F1 DEFECT, PINNED. F1 shipped this tag unconditionally and called the feature
    // "flag-gated", but the flag only hid the CONTROL. The script still ran everywhere, and its
    // default is `auto` — which follows the device — so every visitor whose computer was set to
    // dark got a dark product across surfaces no sprint had repainted. It was reported from the
    // live sponsor page, not caught here.
    //
    // With the flag off there must be NO script, so no `data-theme` attribute exists, so the dark
    // ramp cannot match and every page is light. Inert, not merely invisible.
    const layout = read('src/app/layout.tsx')
    const head = layout.slice(layout.indexOf('<head>'), layout.indexOf('</head>'))
    const tagAt = head.indexOf('<script')
    expect(tagAt).toBeGreaterThan(-1)
    // The guard has to sit BEFORE the tag and wrap it — not merely appear somewhere in the file.
    const guardAt = head.indexOf('themeSwitchEnabled()')
    expect(guardAt).toBeGreaterThan(-1)
    expect(guardAt).toBeLessThan(tagAt)
  })

  it('is loaded render-blocking from the head, not deferred and not in the body', () => {
    // If this ever becomes `defer`, `async`, or moves into <body>, the flash comes back and no
    // other test would notice — the page still works, it just looks wrong for a moment on every
    // navigation, which is exactly the class of bug that survives a green suite.
    const layout = read('src/app/layout.tsx')
    const head = layout.slice(layout.indexOf('<head>'), layout.indexOf('</head>'))
    expect(head).toContain('THEME_BOOT_SRC')
    // ⚠ Assert against the TAG, never the surrounding block: the comment above it explains why
    // `async` and `defer` are wrong, so a naive search of the whole head matches its own rationale.
    // (It did, on the first run.)
    const tag = head.slice(head.indexOf('<script'), head.indexOf('/>', head.indexOf('<script')) + 2)
    expect(tag).toContain('THEME_BOOT_SRC')
    expect(tag).not.toMatch(/\bdefer\b|\basync\b/)
  })
})

describe('the switch is off by default', () => {
  it('the flag is unset in the environment the tests run in', () => {
    // If this ever fails, someone has turned the theme switch on globally — which, before F6,
    // means an unpainted surface can be put into dark mode by a visitor's own OS setting.
    expect(process.env.NEXT_PUBLIC_THEME_SWITCH).not.toBe('1')
  })
})

describe('the two guards the owner ruled on', () => {
  const css = read('src/app/globals.css')
  const darkBlock = css.slice(css.indexOf(`[${THEME_ATTR}='dark']`))

  const lightBlock = css.slice(css.indexOf(':root {'), css.indexOf(`[${THEME_ATTR}='dark']`))
  const lum = (block: string, name: string) => {
    // ⚠ `\\s` and `\\d`, not `\s`/`\d`: this is a TEMPLATE LITERAL, where `\s` is an unknown
    // escape and collapses to a bare `s` — the regex then silently matches nothing and every
    // luminance assertion throws "no --token". Written wrong once here; the other copies in this
    // file have it right, which is exactly how the mistake survives review.
    const m = block.match(new RegExp(`--${name}:\\s*([\\d ]+);`))
    if (!m) throw new Error(`no --${name} in that block`)
    const [r, g, b] = m[1].trim().split(/\s+/).map(Number)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }

  it('a THEME may never change WHOSE product you are looking at — the identity stop is fixed', () => {
    // ⚠ THIS REPLACES "the dark block contains no --brand-" (Layer 1 F3b, owner direction
    // 2026-08-31). That test enforced the ruling by forbidding the whole family, which also
    // forbade the fix: `--brand-50`..`200` are 95–70% WHITE, so every panel painted with one was a
    // glaring pale patch on a dark page — 101 uses across 40 files — and `800`/`900` were 45–60%
    // BLACK, so text in one was near invisible. The ruling is about IDENTITY, and the identity is
    // `500`: the tenant's actual colour. It is pinned byte-for-byte across the two modes here.
    // The other nine stops are furniture derived from it, and re-aiming furniture at the surface
    // it sits on is not a change of identity.
    const lightBlock = css.slice(css.indexOf(':root {'), css.indexOf(`[${THEME_ATTR}='dark']`))
    const stop = (block: string) => block.match(/--brand-500:\s*([\d ]+);/)?.[1].trim()
    expect(stop(darkBlock)).toBeDefined()
    expect(stop(darkBlock)).toBe(stop(lightBlock))
  })

  it('aims the brand ramp at the ground it actually sits on — the ends SWAP per mode', () => {
    // The property the pale-patch bug violated, stated as a relationship so any future retune
    // still has to satisfy it. In light the tints are lighter than the brand and the shades are
    // darker; in dark that is reversed, because the tints now mix toward the PAGE and the shades
    // toward white. Pasting the light ramp into the dark block — the exact defect F3 raised —
    // fails this immediately.
    //
    // ⚠ NOT "the tint is lighter than the page": in light mode a 95%-white blue tint is very
    // slightly DARKER than a #f9fafb page, and asserting otherwise fails on correct values. The
    // brand's own 500 is the honest reference point.
    for (const [block, tintIsLighter] of [[lightBlock, true], [darkBlock, false]] as const) {
      const base = lum(block, 'brand-500')
      for (const tint of ['brand-50', 'brand-100', 'brand-200']) {
        if (tintIsLighter) expect(lum(block, tint)).toBeGreaterThan(base)
        else expect(lum(block, tint)).toBeLessThan(base)
      }
      for (const shade of ['brand-800', 'brand-900']) {
        if (tintIsLighter) expect(lum(block, shade)).toBeLessThan(base)
        else expect(lum(block, shade)).toBeGreaterThan(base)
      }
    }
  })

  it('reads its DARK ramp out of brandRamp(), so a tenant gets the same treatment', () => {
    // ⚠ THE DARK BLOCK ONLY. The LIGHT ramp is the platform's exact seeded hexes (Tailwind's blue
    // scale, a byte-identity contract from platform Sprint 6) and is deliberately NOT derived —
    // `brandRamp` says so in as many words and never runs for BrightPath in light mode.
    //
    // Dark is different: it did not exist before, so there was no identity to preserve, and it MUST
    // agree with the function because a tenant's dark ramp is computed by that function at runtime.
    // If these baked values and `brandRamp` disagreed, a tenant's dark mode would quietly differ
    // from the platform's and nothing else would notice.
    const ramp = brandRamp(PLATFORM.brandColour, 'dark')
    for (const [step, triplet] of Object.entries(ramp)) {
      expect(darkBlock).toContain(`--brand-${step}: ${triplet};`)
    }
  })

  it('keeps the dark ground constant in `branding.ts` in step with globals.css', () => {
    // `brandRamp` mixes its dark tints toward the page. That page value is written in two files;
    // this is the test that refuses to let the copies drift.
    const src = read('src/lib/branding.ts')
    const ground = darkBlock.match(/--ground-50:\s*([\d ]+);/)?.[1].trim()
    expect(ground).toBeDefined()
    expect(src).toContain(`const DARK_GROUND: Rgb = [${ground!.split(/\s+/).join(', ')}]`)
  })

  it('the dark set covers every token the light set defines — no half-converted ramp', () => {
    const lightBlock = css.slice(css.indexOf(':root {'), css.indexOf(`[${THEME_ATTR}='dark']`))
    const names = (s: string) => new Set(
      Array.from(s.matchAll(/--(ground|positive|info|caution|critical)-(\d{1,4}):/g), (m) => m[0]),
    )
    const light = names(lightBlock)
    expect(light.size).toBeGreaterThan(50)   // the ramps exist at all
    expect(Array.from(light).filter((n) => !names(darkBlock).has(n))).toEqual([])
  })

  it('the dark ramp is the light ramp reversed, not an independent guess', () => {
    // Pinned because the reversal is what makes the dark set impossible to half-do. If someone
    // hand-edits a stop, that is fine and expected — but this catches a WHOLE ramp drifting out of
    // the relationship, which is the failure that produces a muddled theme nobody can debug.
    const chan = (block: string, name: string) => {
      const m = block.match(new RegExp(`--${name}:\\s*([\\d ]+);`))
      return m ? m[1].trim() : null
    }
    const lightBlock = css.slice(css.indexOf(':root {'), css.indexOf(`[${THEME_ATTR}='dark']`))
    // ⚠ TONES ONLY. The ground ramp was in this list until F2a and is deliberately no longer:
    // a tone is a signal that only has to stay legible when reversed, but the ground carries
    // ROLES (raised surface, page, well, border) that a reversal actively destroys — it put the
    // card BELOW its own page. The ground's guarantee is the ordering test below instead.
    for (const [a, b] of [['positive-50', 'positive-900'], ['critical-100', 'critical-800'],
                          ['info-50', 'info-900'], ['caution-200', 'caution-700']]) {
      expect(chan(darkBlock, a)).toBe(chan(lightBlock, b))
      expect(chan(darkBlock, b)).toBe(chan(lightBlock, a))
    }
  })

  it('lifts the raised surface ABOVE its page, in BOTH modes', () => {
    // ⚠ THE F2a DEFECT, PINNED. `ground-0` is the card, the input, the modal; `ground-50` is the
    // page they lie on. A straight reversal made `ground-0` pure black on a #111827 page, so
    // every card read as a hole punched THROUGH the page rather than a thing resting on it —
    // found by looking, not by a test, because nothing about it is expressible as "a colour is
    // wrong". This is the property that has to hold, whatever numbers a later tuning pass picks.
    const lightBlock = css.slice(css.indexOf(':root {'), css.indexOf(`[${THEME_ATTR}='dark']`))
    const lum = (block: string, name: string) => {
      const m = block.match(new RegExp(`--${name}:\\s*([\\d ]+);`))
      if (!m) throw new Error(`no --${name}`)
      const [r, g, b] = m[1].trim().split(/\s+/).map(Number)
      return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }
    // Light: white card on a near-white page. Dark: a lifted card on a darker page.
    expect(lum(lightBlock, 'ground-0')).toBeGreaterThan(lum(lightBlock, 'ground-50'))
    expect(lum(darkBlock, 'ground-0')).toBeGreaterThan(lum(darkBlock, 'ground-50'))
  })

  it('keeps every ground role distinct, so a well never vanishes into its card', () => {
    // The stops carry roles — 0 raised, 100 well/hover, 200 border, 300 stronger border. Two
    // roles sharing a value is invisible in a screenshot of one component and wrong everywhere
    // else, which is precisely the bug class the reversal produced when `ground-0` moved.
    for (const block of [css.slice(css.indexOf(':root {'), css.indexOf(`[${THEME_ATTR}='dark']`)), darkBlock]) {
      const stops = ['0', '50', '100', '200', '300', '400', '500']
        .map((s) => block.match(new RegExp(`--ground-${s}:\\s*([\\d ]+);`))?.[1].trim())
      expect(stops.filter(Boolean)).toHaveLength(stops.length)
      expect(new Set(stops).size).toBe(stops.length)
    }
  })
})

describe('the stylesheet is a hiding place too', () => {
  // ⚠ FOUND BY LOOKING, IN F2a. Every conversion guard in this file reads `.tsx`. `globals.css`
  // is neither a component nor a surface, so nothing scanned it — and it held `body` painted
  // `bg-white text-gray-900` (a WHITE page in dark mode, product-wide) and a `.input` class with
  // no background at all, which a browser fills with its own white. Both were invisible in light
  // mode and both would have shipped. The colour was in the stylesheet, not the markup.
  const css = read('src/app/globals.css')
  const layers = css.slice(css.indexOf('@layer base'))

  it('has no raw Tailwind colour in the base and component layers', () => {
    // Comments stripped, for the second time in this file and for the same reason: the note
    // explaining WHY `body` no longer says `bg-white text-gray-900` contains the very strings it
    // forbids. A guard that reads source text has to tell code from prose, or the only way to
    // pass it is to stop explaining yourself.
    const offenders = Array.from(new Set(withoutComments(layers).match(new RegExp(RAW, 'g')) ?? []))
      // `orange` has no tone in the vocabulary and is left literal on the grade-badge ramp, on
      // purpose and with the reason written beside it. Anything else here is a miss.
      .filter((c) => !c.includes('-orange-'))
    expect(offenders).toEqual([])
  })

  it('gives every text control an explicit background', () => {
    // The user-agent default is white and it is NOT a colour anyone wrote, so it follows no
    // theme. A control without a background is a light-mode island by omission.
    const input = layers.slice(layers.indexOf('.input {'))
    expect(input.slice(0, input.indexOf('}'))).toMatch(/bg-ground-/)
  })
})

// ── The converted surfaces, one entry per repaint sprint ────────────────────────────────────────

/** F1's surface — the whole sponsor portal, so it can be walked. */
assertConverted(
  'the sponsor portal (F1)',
  [...walkFiles('src/app/sponsor'), ...walkFiles('src/components/sponsors')],
  15,
)

/**
 * F2a's surface — the student-journey half of the shared components.
 *
 * ⚠ A LIST, NOT A WALK, and that is the point: `src/components` is being converted in two halves,
 * so a directory walk here would fail on F2b's files and there would be no guard at all until both
 * landed. When F2b lands it appends to this list; when the list covers the directory it becomes a
 * walk. `ScholarshipDocuments.tsx` is deliberately absent — it belongs to F3 (it alone carries 126
 * chromatic utilities, a third of this directory).
 */
export const F2A_FILES = [
  'src/components/ActionCentre.tsx', 'src/components/ScholarshipNextSteps.tsx',
  'src/components/ScholarshipReview.tsx', 'src/components/AwardComprehensionQuiz.tsx',
  'src/components/AuthGateModal.tsx', 'src/components/FamilyRosterFields.tsx',
  'src/components/IncomeRouteSwitch.tsx', 'src/components/Pagination.tsx',
  'src/components/OrgRequestAttachments.tsx', 'src/components/InfoBox.tsx',
  'src/components/ScholarshipConsent.tsx', 'src/components/AuthButtons.tsx',
  'src/components/FilterPill.tsx', 'src/components/DocViewer.tsx',
  'src/components/IcInput.tsx', 'src/components/InfoTip.tsx',
  'src/components/ProgressStepper.tsx', 'src/components/FundingBar.tsx',
  'src/components/ScholarshipReferee.tsx', 'src/components/ScholarshipBanner.tsx',
  'src/components/Toast.tsx', 'src/components/Toggle.tsx',
  'src/components/FieldLabel.tsx', 'src/components/VerifiedTick.tsx',
  'src/components/DocumentHelpCoach.tsx', 'src/components/SelectWithOther.tsx',
  'src/components/IncomeClusterCoach.tsx',
]

assertConverted('the shared student-journey components (F2a)', F2A_FILES, 27)

/** F2b's surface — the rest of `src/components`, MINUS the four categorical files below. */
export const F2B_FILES = [
  'src/components/AppHeader.tsx', 'src/components/AppFooter.tsx',
  'src/components/SponsorLanding.tsx', 'src/components/SponsorDetailsForm.tsx',
  'src/components/CourseCard.tsx', 'src/components/PathwayPicker.tsx',
  'src/components/CourseDetailShared.tsx', 'src/components/AiReliabilityCard.tsx',
  'src/components/SponsorNotifyPrefs.tsx', 'src/components/ProgrammePicker.tsx',
  'src/components/SchoolSelect.tsx', 'src/components/InstitutionPicker.tsx',
  'src/components/CourseHeader.tsx', 'src/components/PathwaySelect.tsx',
  'src/components/AliranPicker.tsx', 'src/components/PathwayCards.tsx',
  'src/components/LanguageSelector.tsx', 'src/components/ReferralCapture.tsx',
  'src/components/HtmlLang.tsx', 'src/components/BrandLogo.tsx',
]

assertConverted('the remaining shared components (F2b)', F2B_FILES, 20)

/**
 * The four files that carry a CATEGORY PALETTE — a colour per category, whose only job is to be
 * distinct from its neighbours. F2b left them literal because the vocabulary had no name for that
 * kind of colour; F2c added the `category-N` family (owner decision, 2026-08-31) and they are now
 * converted like everything else. The number beside each is how many DISTINCT swatches that
 * file's set requires.
 */
const CATEGORICAL: Record<string, number> = {
  'src/components/PathwayTrackCard.tsx': 5 + 2,  // five fields of study + two pathways
  'src/components/RequirementsCard.tsx': 6 + 1,  // six institution types + the language chip
  'src/components/SpecialConditions.tsx': 7,     // seven entry conditions
  'src/components/CareerPathways.tsx': 1,        // one occupation chip
  // Layer 1 F4 — the admin console's own category palettes.
  'src/lib/roleBadge.ts': 7,                     // seven staff roles, ONE shared copy
  'src/app/admin/students/page.tsx': 2,          // which exam a student sat: STPM / SPM
  'src/app/admin/students/[id]/page.tsx': 1,     // the STPM section's chips (no exam-type badge here)
  'src/app/admin/requests/[id]/page.tsx': 1,     // which component a request is about
  'src/app/admin/billing/page.tsx': 1,           // platform-level, against an organisation
}

assertConverted('the category-palette files (F2c, F4)', Object.keys(CATEGORICAL), 9)

describe('a category palette is a SET, and its members must stay distinguishable', () => {
  // ⚠ THE F2b FINDING, NOW GUARDED PROPERLY. A per-item rename can be right every time and still
  // destroy the set: `poly` (emerald) and `ILJTM` (green) would BOTH have become `positive`, so
  // two institution types a student uses to compare courses would have rendered identically, with
  // nothing failing. The property that matters is not "which colour" but "how many DIFFERENT
  // ones", so that is what is asserted.
  for (const [file, needed] of Object.entries(CATEGORICAL)) {
    it(`${file.split('/').slice(-2).join('/')} uses ${needed} distinct swatches`, () => {
      const used = new Set(
        Array.from(withoutComments(read(file)).matchAll(/\bcategory-(\d)-(?:surface|ink|dot)\b/g),
          (m) => m[1]),
      )
      expect(used.size).toBe(needed)
    })
  }

  it('is a CLOSED list — a fifth categorical file has to be a deliberate addition', () => {
    // Grown deliberately in F4, which is exactly what this test is for: it failed on the five
    // admin additions and made adding them an explicit act rather than a silent one.
    expect(Object.keys(CATEGORICAL).sort()).toEqual([
      'src/app/admin/billing/page.tsx',
      'src/app/admin/requests/[id]/page.tsx',
      'src/app/admin/students/[id]/page.tsx',
      'src/app/admin/students/page.tsx',
      'src/components/CareerPathways.tsx', 'src/components/PathwayTrackCard.tsx',
      'src/components/RequirementsCard.tsx', 'src/components/SpecialConditions.tsx',
      'src/lib/roleBadge.ts',
    ])
  })
})

describe('the category family itself', () => {
  const cssSrc = read('src/app/globals.css')
  const lightBlock = cssSrc.slice(cssSrc.indexOf(':root {'), cssSrc.indexOf(`[${THEME_ATTR}='dark']`))
  const darkBlock = cssSrc.slice(cssSrc.indexOf(`[${THEME_ATTR}='dark']`))
  const NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8]
  const chan = (block: string, name: string) => {
    const m = block.match(new RegExp(`--${name}:\\s*([\\d ]+);`))
    return m ? m[1].trim() : null
  }
  const lum = (block: string, name: string) => {
    const [r, g, b] = (chan(block, name) ?? '0 0 0').split(/\s+/).map(Number)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }

  it('defines all three roles for all eight swatches, in both modes', () => {
    for (const n of NUMBERS) {
      for (const role of ['surface', 'ink', 'dot']) {
        expect(chan(lightBlock, `category-${n}-${role}`)).not.toBeNull()
        expect(chan(darkBlock, `category-${n}-${role}`)).not.toBeNull()
      }
    }
  })

  it('keeps every swatch distinct from every other, in both modes', () => {
    // The entire point of the family. Two swatches sharing a value is the F2b bug reintroduced one
    // level down — and it would be invisible on any page that shows only one of them.
    for (const block of [lightBlock, darkBlock]) {
      const surfaces = NUMBERS.map((n) => chan(block, `category-${n}-surface`))
      expect(new Set(surfaces).size).toBe(NUMBERS.length)
    }
  })

  it('is READABLE: ink contrasts against its own surface, the opposite way in each mode', () => {
    // Light: dark ink on a pale chip. Dark: pale ink on a deep chip. This is a ROLE SWAP, not the
    // reversal the tones use — a chip has to stay a chip. A swatch failing this would be an
    // unreadable chip in exactly one mode, which is the failure a light-only review never sees.
    for (const n of NUMBERS) {
      expect(lum(lightBlock, `category-${n}-ink`))
        .toBeLessThan(lum(lightBlock, `category-${n}-surface`))
      expect(lum(darkBlock, `category-${n}-ink`))
        .toBeGreaterThan(lum(darkBlock, `category-${n}-surface`))
    }
  })

  it('avoids the four tone hues, so a category chip is never mistaken for a status', () => {
    // The swatches are violet / teal / orange / pink / cyan / lime / fuchsia / indigo. Green, blue,
    // amber and red belong to the tones, and a green category chip beside a green "done" badge is
    // exactly the confusion this family exists to prevent. Pinned against the source comments that
    // name each hue, so a retune has to restate the choice rather than drift out of it.
    const block = lightBlock.slice(lightBlock.indexOf('--category-1-surface'),
                                   lightBlock.indexOf('--critical-50'))
    for (const hue of ['violet', 'teal', 'orange', 'pink', 'cyan', 'lime', 'fuchsia', 'indigo']) {
      expect(block).toContain(hue)
    }
    for (const toneHue of ['green-', 'blue-', 'amber-', 'red-']) {
      expect(block).not.toContain(toneHue)
    }
  })
})

/**
 * F3's surface — everything a STUDENT sees, plus the three app-level shells.
 *
 * A directory walk, not a list: `src/app/scholarship`, `/profile`, `/onboarding`, `/dashboard`,
 * `/saved`, `/settings`, `/verify-email` and `/report` are converted in full, so the guard should
 * fail on a NEW page in any of them rather than quietly ignore it — which a hand-list would.
 * `ScholarshipDocuments.tsx` joins them from `src/components`: it is a student surface that
 * happens to live with the shared components, and at 288 utilities it was the largest single file
 * in the product.
 *
 * `error` / `loading` / `not-found` are here because they carried the same `bg-[#f8fafc]` page
 * ground as the student pages and would otherwise have been a white flash in dark mode at the
 * exact moment something has already gone wrong.
 */
const F3_DIRS = [
  'src/app/scholarship', 'src/app/profile', 'src/app/onboarding', 'src/app/dashboard',
  'src/app/saved', 'src/app/settings', 'src/app/verify-email', 'src/app/report',
]

export const F3_FILES = [
  ...F3_DIRS.flatMap((d) => walkFiles(d)).map((f) => f.split(path.sep).join('/')),
  'src/components/ScholarshipDocuments.tsx',
  'src/app/error.tsx', 'src/app/loading.tsx', 'src/app/not-found.tsx',
]

assertConverted('the student surfaces (F3)', F3_FILES, 20)

/**
 * F4 + F5's surface — the WHOLE admin console, cockpit included.
 *
 * A walk, so a new admin page is caught the day it is added. The officer cockpit
 * (`admin/scholarship/[id]`) was excluded here through F4 and ceilinged at 544; **F5 converted it,
 * so the exclusion and the ceiling are both gone** and it is now simply one of the files below.
 */
export const F4_FILES = [
  ...walkFiles('src/app/admin').map((f) => f.split(path.sep).join('/')),
  ...walkFiles('src/components/admin').map((f) => f.split(path.sep).join('/')),
  'src/lib/roleBadge.ts',
]

assertConverted('the admin console, cockpit included (F4 + F5)', F4_FILES, 41)

describe('the F4 semantic corrections the codemod could not make', () => {
  it('paints every filled control in the console with the BRAND — all 38 of them', () => {
    // ⚠ THE LARGEST INSTANCE OF THE F1 DEFECT SO FAR, and the clearest argument for the rule. The
    // console's primary button is `bg-info-600 text-white`, used 38 times across 17 files. Left as
    // a tone, a tenant's colour would have reached almost nothing on the surface their own staff
    // use all day. An info NOTICE (`bg-info-50` with dark text) is untouched — the distinction is
    // "filled control the user ACTS on" versus "coloured surface that INFORMS".
    // ⚠ THE ESCAPES BELOW ARE WRITTEN BY HAND, NOT GENERATED. The first version of this guard
    // came out of a script, and \b inside that script's own string became a literal BACKSPACE
    // byte: the regex still compiled, matched nothing, and the guard passed forever. Bite-
    // checking is the only reason it was ever found. Code that writes code has its escapes
    // eaten twice, and the failure is silent — a dead guard, not a broken build.
    const offenders: string[] = []
    for (const f of F4_FILES) {
      if (!f.endsWith('.tsx')) continue
      for (const line of withoutComments(read(f)).split('\n')) {
        if (/\btext-white\b/.test(line) && /\bbg-info-[567]00\b/.test(line)) {
          offenders.push(`${f}: ${line.trim()}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('keeps ONE copy of the role palette, which is why it cannot desynchronise', () => {
    // Three files declared this mapping independently, the third with a comment asking that they
    // agree. F4's codemod converted one copy's `amber` to `caution` and left the others, and they
    // silently stopped agreeing — the same role would have rendered one colour in Administration
    // and another in the Manual. A comment is not a mechanism; a shared module is.
    for (const f of ['src/components/admin/StaffAdmin.tsx',
                     'src/app/admin/organisation/reviewers/page.tsx',
                     'src/app/admin/guide/page.tsx']) {
      expect(read(f)).toMatch(/roleBadgeClass/)
      // …and none of them may re-declare a palette of its own.
      expect(withoutComments(read(f))).not.toMatch(/'bg-category-\d-surface text-category-\d-ink'/)
    }
  })

  it('says "suspended" and "declined" inside the vocabulary, by WEIGHT', () => {
    // Two more sets that needed a state the four tones do not name outright. `suspended` is a
    // HOLD — nearer to `pending` than to `rejected` — so it is `caution` at a heavier weight, the
    // same move F3 made for `graduated`. `declined` (a reviewer's call) is `caution` against
    // `rejectedAfterReview` (the case's fate), which stays `critical`.
    expect(read('src/app/admin/sponsors/page.tsx')).toMatch(/'bg-caution-600 text-white'/)
    expect(read('src/app/admin/organisation/reviewers/[id]/page.tsx')).toMatch(/declined: 'bg-caution-500'/)
    expect(read('src/app/admin/organisation/reviewers/[id]/page.tsx')).toMatch(/rejectedAfterReview: 'bg-critical-500'/)
  })
})

describe('the F5 semantic corrections the codemod could not make', () => {
  // The cockpit's ceiling (544) is GONE, not lowered: F5 converted the file, so it is covered by
  // the conversion guard above like every other admin page. A ratchet that guards a converted
  // surface is noise — the same reason F3 deleted the `src/components` one.
  const cockpit = 'src/app/admin/scholarship/[id]/page.tsx'

  it('paints its two Save buttons with the BRAND, like the other 38 in the console', () => {
    const src = withoutComments(read(cockpit))
    expect(src).not.toMatch(/bg-info-600[^"']*text-white/)
    expect((src.match(/bg-primary-600/g) ?? []).length).toBeGreaterThanOrEqual(2)
  })

  it('separates "unrelated name" from a generic vision warning', () => {
    // Both are notes in the same block. `caution-600` is the generic warning; a utility bill in an
    // unrelated person's name is evidence the document may not belong to this household at all,
    // and orange used to hold them apart. Sharing a tone would have flattened the distinction the
    // officer most needs to see.
    const src = read(cockpit)
    expect(src).toMatch(/text-critical-600[^]{0,400}utilityNote\.unrelated/)
    expect(src).toMatch(/text-caution-600[^]{0,120}vision_fields\.warnings/)
  })

  it('treats "how was this value produced" as a CATEGORY, and the AI briefing as INFO', () => {
    // Two provenance kinds — read deterministically, or derived by a model — so the neutral one
    // keeps the ground and the other takes one swatch. The Check-2 case summary is a different
    // thing: a briefing whose JOB is to inform, so it is the info tone and its heading carries the
    // "a model wrote this" claim. Colour should not be doing that work.
    const src = read(cockpit)
    expect(src).toMatch(/bg-category-1-surface text-category-1-ink/)
    expect(src).toMatch(/border-info-100 bg-info-50\/60/)
  })

  it('keeps the HOLD badge filled, the same as a suspended sponsor in F4', () => {
    // A circuit-breaker stopped the loop and a human has to look. It sits beside a grey `kind`
    // chip, so a tint would have read as its quiet neighbour.
    expect(read(cockpit)).toMatch(/bg-caution-600 px-1\.5 py-0\.5 text-\[11px\] font-semibold text-white/)
  })
})

describe('the colour a class scan cannot see, on the student surfaces', () => {
  // ⚠ THREE SPRINTS, THREE NEW HIDING PLACES. F1 found inline `conic-gradient` hex; F2a found the
  // stylesheet's own `body` rule and a text control with no background at all; F3 found these two.
  // Every one of them was invisible to a scan that reads Tailwind class names, and every one of
  // them would have been a light-mode island in a dark product.

  it('has no ARBITRARY-VALUE colour class — `bg-[#f8fafc]` is a class, not a colour', () => {
    // The subtlest of the three. `bg-[#f8fafc]` passes any check that looks for `bg-gray-50`,
    // because it IS a class and it is not on the list. Six pages set their whole page ground this
    // way, including the error and loading screens.
    const offenders: string[] = []
    for (const f of F3_FILES) {
      for (const m of withoutComments(read(f)).match(/-\[#[0-9a-fA-F]{3,8}\]/g) ?? []) {
        offenders.push(`${f}: ${m}`)
      }
    }
    expect(offenders).toEqual([])
  })

  it('has no raw hex in an SVG attribute — those are props, not classes', () => {
    // `stroke="#3b82f6"` is a React prop. No codemod over class names will ever touch it, and it
    // was a HARDCODED blue: the stream icons never followed a tenant's brand either, even sitting
    // inside a `bg-primary-500` button. They read `rgb(var(--brand-500))` now.
    const GOOGLE_LOGO_HEXES = ['#4285F4', '#34A853', '#FBBC05', '#EA4335']
    const offenders: string[] = []
    for (const f of F3_FILES) {
      for (const hex of withoutEntities(withoutComments(read(f))).match(/#[0-9a-fA-F]{3,8}\b/g) ?? []) {
        if (!GOOGLE_LOGO_HEXES.includes(hex.toUpperCase())) offenders.push(`${f}: ${hex}`)
      }
    }
    expect(offenders).toEqual([])
  })
})

describe('the F3 semantic corrections the codemod could not make', () => {
  it('paints the onboarding progress steps with the BRAND, like every other progress marker', () => {
    // Fourth sprint running that the codemod called a piece of product furniture "information".
    // The shared `ProgressStepper` and the sponsor landing's step numbers were already `primary`;
    // this one would have left a tenant's colour reaching two of the three.
    const src = read('src/app/scholarship/onboarding/page.tsx')
    expect(src).toMatch(/bg-primary-600 text-white/)
    expect(withoutComments(src)).not.toMatch(/bg-info-600/)
    expect(read('src/components/ProgressStepper.tsx')).toMatch(/bg-primary-500/)
  })

  it('distinguishes "graduated" from "on track" by WEIGHT, both still positive', () => {
    // `graduated` was `indigo` — outside the vocabulary — because the set needs two good states a
    // student can tell apart. A category swatch would have been wrong (it IS a state); a second
    // tone would have lied about it. Same tone, filled instead of tinted.
    const src = read('src/app/scholarship/in-programme/page.tsx')
    expect(src).toMatch(/graduated: 'bg-positive-600 text-white'/)
    expect(src).toMatch(/on_track: 'bg-positive-100 text-positive-700'/)
    expect(withoutComments(src)).not.toMatch(/indigo/)
  })
})
