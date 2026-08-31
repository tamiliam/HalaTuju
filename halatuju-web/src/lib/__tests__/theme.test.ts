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
        for (const hex of withoutComments(read(f)).match(/#[0-9a-fA-F]{3,8}\b/g) ?? []) {
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

  it('a THEME may never write the tenant brand', () => {
    // --brand-* is the ORGANISATION's identity. A mode that rewrote it would mean switching to dark
    // silently changed whose product you are looking at.
    expect(darkBlock).not.toMatch(/--brand-/)
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
    for (const [a, b] of [['ground-0', 'ground-1000'], ['ground-50', 'ground-900'],
                          ['positive-50', 'positive-900'], ['critical-100', 'critical-800']]) {
      expect(chan(darkBlock, a)).toBe(chan(lightBlock, b))
      expect(chan(darkBlock, b)).toBe(chan(lightBlock, a))
    }
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

describe('the F2a semantic corrections the codemod could not make', () => {
  // ⚠ THE F1 LESSON, PINNED. The codemod renames a colour correctly and can classify it wrongly:
  // it turned the sponsor portal's primary call-to-action into `info`, which both reversed badly in
  // dark AND meant a tenant's colour could never reach it. The rule that resolved it — a filled
  // control the user ACTS on carries the BRAND; a coloured surface that INFORMS carries the tone —
  // has no mechanical test, so the two judgements F2a actually made are pinned by name instead.

  it('paints the funding progress bar with the BRAND, like its twin in the Action Centre', () => {
    // Not a semantic state: a progress fill is this product measuring its own progress. Left as
    // `info` a tenant would set their colour and watch ONE of the two bars follow it.
    expect(read('src/components/FundingBar.tsx')).toMatch(/bg-primary-600/)
    expect(read('src/components/FundingBar.tsx')).not.toMatch(/bg-info-/)
    expect(read('src/components/ActionCentre.tsx')).toMatch(/bg-primary-500/)
  })

  it('keeps the "done" medallions and the toast on their TONES, not the brand', () => {
    // The mirror of the rule, and the reason it is not "make everything brand": these DO carry a
    // semantic state. A tenant's colour must never repaint "this succeeded".
    expect(read('src/components/ActionCentre.tsx')).toMatch(/bg-positive-600 text-sm text-white/)
    expect(read('src/components/Toast.tsx')).toMatch(/bg-positive-600 text-white/)
    expect(read('src/components/Toast.tsx')).toMatch(/bg-critical-600 text-white/)
  })
})

describe('the unconverted shared components — a ceiling that may only fall', () => {
  // F2b's half, waiting. This is not a conversion guard: it is a RATCHET. It stops raw colour being
  // ADDED to a surface a later sprint still has to repaint, and it can only ever be lowered — when
  // F2b lands, this count goes to zero and the block goes away.
  //
  // ⚠ SCOPED TO F2b's OWN FILES — `src/components/*` only, no subdirectories. `components/admin`
  // belongs to F4 and `components/sponsors` is already done. Ratcheting a directory that no sprint
  // has scheduled would freeze the colours of a console people are still building features on, and
  // the next ordinary admin page would fail this test with no sanctioned way to pass it.
  const rest = walkFiles('src/components')
    .map((f) => f.split(path.sep).join('/'))
    .filter((f) => f.split('/').length === 3)   // src/components/X.tsx — top level only
    .filter((f) => !F2A_FILES.includes(f))

  /** Measured 2026-08-31, immediately after F2a converted its 27 files. LOWER THIS, NEVER RAISE IT. */
  const CEILING = 659

  it('has not grown', () => {
    const count = rest.reduce(
      (n, f) => n + (read(f).match(new RegExp(RAW, 'g'))?.length ?? 0), 0,
    )
    // A failure here is almost never "raise the number". It means new hand-written colour landed on
    // a surface that is queued for conversion — write it on the tokens instead, the way F2a's files
    // now are. Lower the ceiling when a sprint converts more of the directory.
    expect(count).toBeLessThanOrEqual(CEILING)
  })
})
