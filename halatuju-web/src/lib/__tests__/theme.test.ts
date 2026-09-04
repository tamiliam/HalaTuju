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
 * The ONE file allowed to write a colour down, and the one value it may write (Layer 1 F6).
 *
 * `branding.ts` holds the platform's own brand colour, which every ramp in the product is derived
 * FROM. It has to be a literal somewhere or there is nothing to derive. The exemption is scoped to
 * the file AND the value, not to hex in general, so a second colour appearing in that file still
 * fails — this is a definition, not a licence.
 */
const COLOUR_DEFINITIONS: Record<string, string[]> = {
  'src/lib/branding.ts': ['#137FEC'],
}

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
      // ⚠ COMMENTS STRIPPED, same as the hex scan below and for the same reason (F2a's lesson).
      // F6's note explaining why the state tint was removed has to name `bg-gray-50` to explain
      // it; without this the only way to pass the guard is to stop writing down what changed.
      const offenders = files
        .map((f) => [f, withoutComments(read(f)).match(new RegExp(RAW, 'g'))] as const)
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
        const allowed = COLOUR_DEFINITIONS[f] ?? []
        for (const hex of withoutEntities(withoutComments(read(f))).match(/#[0-9a-fA-F]{3,8}\b/g) ?? []) {
          const up = hex.toUpperCase()
          if (!GOOGLE_LOGO.has(up) && !allowed.includes(up)) offenders.push(`${f}: ${hex}`)
        }
      }
      expect(offenders).toEqual([])
    })

    it('keeps white literal — it must NOT invert with the ground', () => {
      // 214 uses across the product, nearly all on a coloured or dark surface: a button label, a
      // filled badge, the tick inside a seal. Mapped onto --ground-0 they turn black in dark mode.
      // The codemod converts BACKGROUND white only; this asserts the distinction survived here.
      // ⚠ COMMENTS STRIPPED — `contrast.ts` explains this very rule in prose and quotes both sides
      // of it, so the unstripped version accused the sentence describing the invariant.
      const withWhite = files.filter((f) => /\b(?:text|stroke|border|ring)-white\b/.test(withoutComments(read(f))))
      expect(withWhite.length).toBeGreaterThan(0)
      for (const f of withWhite) expect(withoutComments(read(f))).not.toMatch(/\b(?:text|stroke)-ground-0\b/)
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

  it('IS UNCONDITIONAL — THE FLIP (Layer 1 F7d)', () => {
    // ⚠ THIS TEST ASSERTED THE EXACT OPPOSITE FOR THE WHOLE ARC, and both versions were right in
    // their turn. F1 shipped the tag unconditionally while calling the feature "flag-gated" — but
    // the flag only hid the CONTROL. The script still ran everywhere with a default of `auto`,
    // which follows the device, so every visitor whose computer was set to dark got a dark product
    // across surfaces no sprint had repainted. Reported from the live sponsor page, not caught
    // here. The fix was to gate the SCRIPT, and this test pinned that.
    //
    // F7d removes the gate because its condition is met: every surface is converted, the ramp
    // carries both modes with no exemptions, the last unopened screen was mounted and fixed, and
    // `ThemeSelector` exists. **Keep the lesson even though the flag is gone: a flag that gates
    // only the affordance gates nothing.**
    const layout = read('src/app/layout.tsx')
    const head = layout.slice(layout.indexOf('<head>'), layout.indexOf('</head>'))
    expect(head).toContain('<script')
    // Comments are stripped first: the rationale above the tag NAMES the deleted function, and a
    // raw search of the head would match its own explanation. (It did, on the first run — the same
    // shape of self-match the `defer`/`async` test below already documents.)
    const code = head.replace(/\{?\/\*[\s\S]*?\*\/\}?/g, ' ')
    expect(code).not.toContain('themeSwitchEnabled')
    // Nothing may CONDITION the tag — not this flag and not a future one. Anything rendering the
    // script behind a `&&` or a `?` puts a whole class of visitor back on an unthemed page.
    const before = code.slice(0, code.indexOf('<script'))
    expect(before).not.toMatch(/&&|\?/)
  })

  it('leaves no trace of the flag anywhere in the source', () => {
    // A deleted flag that survives in one call site is worse than no flag: the switch is reachable
    // but one surface silently is not. Scans everything, not the layout alone.
    // ⚠ THIS FILE IS EXCLUDED, AND ONLY THIS FILE. It has to spell the flag out to search for it,
    // so a scan that includes itself can only ever fail. Naming the exclusion narrowly is the
    // point — a scan that quietly skipped `__tests__` would also stop noticing a live call site
    // that a test happens to sit beside.
    const SELF = 'src/lib/__tests__/theme.test.ts'
    const offenders: string[] = []
    const walk = (dir: string) => {
      for (const e of fs.readdirSync(path.join(process.cwd(), dir))) {
        const rel = `${dir}/${e}`
        if (rel === SELF) continue
        if (fs.statSync(path.join(process.cwd(), rel)).isDirectory()) walk(rel)
        else if (/\.(ts|tsx|js)$/.test(e)) {
          const src = read(rel).replace(/\{?\/\*[\s\S]*?\*\/\}?/g, ' ').replace(/\/\/.*/g, ' ')
          if (src.includes('NEXT_PUBLIC_THEME_SWITCH') || src.includes('themeSwitchEnabled')) {
            offenders.push(rel)
          }
        }
      }
    }
    walk('src')
    // Self-check: a broken walk must not pass on nothing.
    expect(fs.readdirSync(path.join(process.cwd(), 'src')).length).toBeGreaterThan(0)
    expect(offenders).toEqual([])
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

describe('the switch a person can actually click (Layer 1 F7d)', () => {
  // ⚠ THIS DESCRIBE ASSERTED THE FLAG WAS OFF FOR THE WHOLE ARC. It is the sprint's central fact
  // inverted: dark mode was complete and unreachable, and F7d's job was to make it reachable. A
  // test that says "off by default" would now pass forever while nobody could use the feature.

  const selector = read('src/components/ThemeSelector.tsx')

  it('offers exactly the three modes the module defines, and names none of them itself', () => {
    // The options are generated from THEME_MODES, so a fourth mode cannot appear in one place and
    // not the other. Hard-coded English in a `<option>` is the failure this catches — the product
    // ships in three languages and the arc has already shipped one untranslated control.
    expect(selector).toContain('THEME_MODES.map')
    for (const m of THEME_MODES) {
      expect(selector).not.toMatch(new RegExp(`>\\s*${m}\\s*<`, 'i'))
    }
  })

  it('writes the mode to storage — the choice is DEVICE-LOCAL, by the owner\'s ruling', () => {
    // Owner, 2026-09-02: device-local, no account storage. Language is a larger per-person choice
    // and is already device-local, so a MORE persistent theme would be backwards. F1b as scoped —
    // four settings surfaces, three identity models, a migration — is superseded, not deferred.
    expect(selector).toContain('writeStoredMode')
    // No account call may creep in later. This is the assertion that would fail if it did.
    expect(selector).not.toMatch(/fetch\(|useMutation|api\./)
  })

  it('does NOT re-apply a theme on mount — the boot script already did', () => {
    // Two things setting `data-theme` can only ever disagree. The sandbox toggle had to apply on
    // mount because the script was gated off; that reason died with the flag.
    // ⚠ Anchor on the CALL, not the identifier: `useEffect` first appears in the import line, so
    // slicing from there swallows the whole import list — including `applyTheme`, which `pick`
    // legitimately uses. The first draft did exactly that and failed on its own imports.
    const mountEffect = selector.slice(selector.indexOf('useEffect(() =>'), selector.indexOf('const pick'))
    expect(mountEffect).toContain('readStoredMode')
    expect(mountEffect).not.toContain('applyTheme')
  })

  it('is mounted on every shell a person can be in', () => {
    // The defect this prevents is silent and partial: the control exists, so the feature looks
    // shipped, but one population — sponsors, or reviewers — has no way to reach it.
    const SHELLS = [
      'src/components/AppHeader.tsx',        // students and the public
      'src/components/admin/Topbar.tsx',     // reviewers, org admins, the officer cockpit
      'src/app/sponsor/(portal)/layout.tsx', // sponsors, who have no settings page at all
      'src/app/page.tsx',                    // the landing page, which draws its own nav
      'src/app/settings/page.tsx',           // where a person goes looking for it
    ]
    const missing = SHELLS.filter((f) => !read(f).includes('<ThemeSelector />'))
    expect({ missing }).toEqual({ missing: [] })
  })

  it('keeps `auto` live for the whole tab, from the provider stack and not from the control', () => {
    // A chromeless page renders no header. Document upload is one, and it is exactly the screen
    // someone sits on for a long time — long enough for a device to reach its own sunset.
    expect(read('src/app/providers.tsx')).toContain('<ThemeWatcher />')
    const watcher = read('src/components/ThemeWatcher.tsx')
    expect(watcher).toContain("addEventListener('change'")
    expect(watcher).toContain('removeEventListener')
    // Re-reads storage in the handler rather than closing over state, so switching to `dark` and
    // back to `auto` cannot leave a stale subscription behind.
    expect(watcher).toContain('readStoredMode')
  })

  it('is the ONE control — the sandbox no longer keeps a copy of it', () => {
    // `sandbox-safety.test.ts` states the rule; this states the specific instance, because the
    // sandbox's segmented toggle was legitimate right up until the real control shipped.
    expect(fs.existsSync(path.join(process.cwd(), 'src/sandbox/ThemeToggle.tsx'))).toBe(false)
    expect(read('src/app/sandbox/layout.sandbox.tsx')).toContain('<ThemeSelector />')
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

  it('THE BRAND ROLES ARE DESCRIBED IN THREE FILES AND ALL THREE MUST AGREE', () => {
    // ⚠ THE F4 ROLE-PALETTE SHAPE, ARRIVING BEFORE IT COULD BITE. `--brand-fill*` and
    // `--brand-shape` are declared in globals.css (what the browser paints), `BRAND_ROLE` in
    // branding.ts (what the picker measures) and `BRAND_ROLE` in contrast.py (what the SAVE PATH
    // measures). If the CSS said one stop and the gate another, a tenant would be approved on a
    // button nobody would ever see — and the failure is silent in both directions. A comment
    // asking them to agree is a request; ONE table per language, pinned, is a rule.
    const lightBlock = css.slice(0, css.indexOf(`[${THEME_ATTR}='dark']`))
    const stop = (block: string, role: string) =>
      block.match(new RegExp(`--brand-${role}:\\s*var\\(--([a-z0-9-]+)\\)`))?.[1]

    expect(stop(lightBlock, 'fill')).toBe('brand-600')
    expect(stop(lightBlock, 'fill-hover')).toBe('brand-700')
    expect(stop(lightBlock, 'shape')).toBe('brand-500')
    expect(stop(darkBlock, 'fill')).toBe('brand-800')
    expect(stop(darkBlock, 'fill-hover')).toBe('brand-900')
    expect(stop(darkBlock, 'shape')).toBe('brand-600')

    // Light's ink is a literal (white), dark's is the page it punches through.
    expect(lightBlock).toMatch(/--brand-fill-ink:\s*255 255 255;/)
    expect(stop(darkBlock, 'fill-ink')).toBe('ground-50')

    // …and the TypeScript half says the same, in the numbers the picker actually resolves.
    const ts = read('src/lib/branding.ts')
    expect(ts).toContain("light: { fill: 600, hover: 700, ink: 'white', shape: 500 }")
    expect(ts).toContain("dark: { fill: 800, hover: 900, ink: 'ground-50', shape: 600 }")
  })

  it('never lets the fill role resolve to the stop a LINK uses', () => {
    // The property behind F7a, stated so a later tuning pass cannot undo it by accident: a button
    // and a link may not share a stop in dark, because on a dark card one has to be pale enough to
    // read as text and the other dark enough to carry ink.
    const ts = read('src/lib/branding.ts')
    const fill = ts.match(/dark: \{ fill: (\d+)/)?.[1]
    expect(fill).toBeDefined()
    // `link_on_card` measures `brand-600`; the fill must be a different, paler stop.
    expect(Number(fill)).toBeGreaterThan(600)
  })

  it('never lets the SHAPE role sit on the identity stop in dark', () => {
    // F7b's property. `brand-500` is byte-identical across modes by ruling, so a dark tenant colour
    // drawn at the identity stop is a dark mark on a dark card — 10 of 18 realistic colours under
    // 3.0. The role must land somewhere paler in dark, and must NOT move in light.
    const ts = read('src/lib/branding.ts')
    expect(ts).toMatch(/light: \{[^}]*shape: 500/)
    const dark = ts.match(/dark: \{[^}]*shape: (\d+)/)?.[1]
    expect(Number(dark)).toBeGreaterThan(500)
    // …and the identity stop itself is untouched by any of this.
    expect(brandRamp('#1e3a8a', 'light')[500]).toBe(brandRamp('#1e3a8a', 'dark')[500])
  })

  it('never reaches for the identity stop from a COMPONENT', () => {
    // ⚠ FOUND BY BITE-CHECKING, AND IT WAS A MISSING GUARD RATHER THAN A BROKEN ONE. The two-tone
    // stream icons stroke themselves with `rgb(var(--brand-500))` as an SVG PROP — F3's hiding
    // place, invisible to every class scan — so on a dark card a dark tenant colour drew an
    // invisible icon. F7b moved it to the role, and then nothing failed when the change was
    // reverted, which is the tell that no test owned it.
    //
    // `--brand-500` is the identity stop: it is byte-identical across modes BY RULING, so anything
    // that must stay visible in both cannot read it directly. Reading it from a component is
    // therefore always a bug — the roles exist precisely so nobody has to.
    const offenders: string[] = []
    for (const f of ALL_FILES) {
      if (f === 'src/lib/branding.ts' || f === 'src/lib/contrast.ts') continue  // the ramp's home
      if (/var\(--brand-500\)/.test(withoutComments(read(f)))) offenders.push(f)
    }
    expect(offenders).toEqual([])
  })

  it('keeps brand TEXT off the shape stop — F7b\'s second finding', () => {
    // ⚠ A LIVE LIGHT-MODE DEFECT, found by classifying rather than by the gate. 31 uses spelled
    // brand text `text-primary-500`, and the platform's own colour measures **3.98** there against
    // white — below AA — in eleven places at `text-sm` or smaller. The gate could not see it
    // because the only pair reading `-500` was scoped as a non-text shape at 3.0. Brand text is
    // `-600` now, which both link pairs already used and which passes in both modes.
    const offenders: string[] = []
    for (const f of ALL_FILES) {
      if (/\btext-primary-500\b/.test(withoutComments(read(f)))) offenders.push(f)
    }
    expect(offenders).toEqual([])
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

  // ── the ink stops must be READABLE, not merely distinct (Layer 1 F7e, 2026-09-04) ──────────
  //
  // ⚠ THIS FILE PASSED THROUGHOUT TD-224, AND TD-224 WAS 263 FAILING ELEMENTS LIVE IN LIGHT MODE.
  // The distinctness test above asks whether two stops share a VALUE; nothing here asked whether
  // a stop a person has to READ can be read. `contrast.py` did not cover it either — its pairs are
  // all brand-versus-ground. **A gate is blind to every pair it does not name**, and this is the
  // fourth time this arc has written that sentence, so this time the pairs are named.

  /** WCAG relative luminance — the real curve, not the linear approximation used for ordering. */
  const rel = (rgb: number[]) => {
    const [r, g, b] = rgb.map((v) => {
      const s = v / 255
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  const contrast = (a: number[], b: number[]) => {
    const [hi, lo] = [rel(a), rel(b)].sort((x, y) => y - x)
    return (hi + 0.05) / (lo + 0.05)
  }
  const rgbOf = (block: string, name: string) => {
    const m = block.match(new RegExp(`--${name}:\\s*([\\d ]+);`))
    if (!m) throw new Error(`no --${name}`)
    return m[1].trim().split(/\s+/).map(Number)
  }
  const lightBlockOf = () => css.slice(css.indexOf(':root {'), css.indexOf(`[${THEME_ATTR}='dark']`))

  it('keeps every INK stop above AA on the tightest ground it sits on, in BOTH modes', () => {
    // ⚠ THE GROUND THAT MATTERS IS THE WELL (`ground-100`), NOT THE CARD. Muted ink appears on a
    // card, on the page, and inside wells/striped rows/hover states — and the well is the closest
    // of the three to the ink, so it is the one that decides. Measuring against the card is how
    // `ground-500` sat at a comfortable-looking 4.83 while the chips it painted read 4.39.
    //
    // 300 is deliberately NOT in this list: it is a border, and WCAG's 4.5 bar is for text.
    for (const [mode, block] of [['light', lightBlockOf()], ['dark', darkBlock]] as const) {
      const well = rgbOf(block, 'ground-100')
      for (const stop of ['400', '500', '600', '700', '800', '900']) {
        const ratio = contrast(rgbOf(block, `ground-${stop}`), well)
        expect(`${mode} ground-${stop} on a well: ${ratio.toFixed(2)}`)
          .toBe(`${mode} ground-${stop} on a well: ${Math.max(ratio, 4.5).toFixed(2)}`)
      }
    }
  })

  it('keeps the ink ramp MONOTONIC, so a later tuning cannot invert two stops', () => {
    // F7e moved 400 and 500 in light and 400 in dark. Without this, moving one stop past its
    // neighbour is a silent reordering: `text-ground-500` would render LIGHTER than
    // `text-ground-400`, and every "muted, but a bit stronger" pairing in the product inverts
    // with nothing failing.
    for (const [mode, block] of [['light', lightBlockOf()], ['dark', darkBlock]] as const) {
      const inks = ['400', '500', '600', '700', '800', '900']
        .map((s) => contrast(rgbOf(block, `ground-${s}`), rgbOf(block, 'ground-100')))
      for (let i = 1; i < inks.length; i += 1) {
        expect(`${mode} ${i}: ${inks[i] > inks[i - 1]}`).toBe(`${mode} ${i}: true`)
      }
    }
  })

  it('⚠ never lets a filled control be spelled as a tone STOP again', () => {
    // THE DEFECT THIS SPRINT EXISTS FOR, made unspellable. `bg-positive-600 text-white` was the
    // cockpit's Accept button: **3.30** in light and **1.40** in dark. F7a built exactly this
    // role for the BRAND and stopped there; the four tone ramps reverse identically and were
    // given neither it nor F7b's move of small text off `-500`. The pattern was named twice and
    // generalised zero times, so this is the guard that makes the third time impossible.
    //
    // The pair `bg-<tone>-<mid stop>` + `text-white` IS the definition of a filled control. A
    // tinted NOTICE (`bg-info-50` with dark ink) is a different thing and deliberately untouched.
    const offenders: string[] = []
    for (const f of walkFiles('src').filter((p) => /\.tsx?$/.test(p))) {
      if (f.includes('__tests__')) continue
      for (const line of withoutComments(read(f)).split('\n')) {
        if (!line.includes('text-white')) continue
        if (/bg-(?:positive|caution|critical|info)-(?:400|500|600|700|800)/.test(line)) {
          offenders.push(`${f}: ${line.trim().slice(0, 120)}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('⚠ keeps every tone FILL readable in BOTH modes, ink and edge alike', () => {
    // Two bars, and a fill has to clear both: its INK needs 4.5 (it carries words) and the fill
    // itself needs 3.0 against the card it sits on (it has to look like a control). F7a's whole
    // finding was that these squeeze from opposite ends — moving `brand-400` let white ink read
    // at 5.82 and dropped the button to 2.52 against its own card. Assert both, or "fixing" one
    // silently breaks the other.
    for (const [mode, block] of [['light', lightBlockOf()], ['dark', darkBlock]] as const) {
      const card = rgbOf(block, 'ground-0')
      for (const tone of ['positive', 'caution', 'critical', 'info']) {
        // `--positive-fill: var(--positive-700)` — follow the indirection to the stop it names.
        const stop = block.match(new RegExp(`--${tone}-fill:\\s*var\\(--${tone}-(\\d+)\\)`))?.[1]
        expect(`${mode} ${tone} fill resolves: ${!!stop}`).toBe(`${mode} ${tone} fill resolves: true`)
        const fill = rgbOf(block, `${tone}-${stop}`)
        const inkRaw = block.match(new RegExp(`--${tone}-fill-ink:\\s*([^;]+);`))![1].trim()
        const ink = inkRaw.startsWith('var(')
          ? rgbOf(block, inkRaw.slice(6, -1))          // var(--ground-50) → ground-50
          : inkRaw.split(/\s+/).map(Number)
        const onFill = contrast(ink, fill)
        const onCard = contrast(fill, card)
        expect(`${mode} ${tone} ink: ${onFill.toFixed(2)}`)
          .toBe(`${mode} ${tone} ink: ${Math.max(onFill, 4.5).toFixed(2)}`)
        expect(`${mode} ${tone} edge: ${onCard.toFixed(2)}`)
          .toBe(`${mode} ${tone} edge: ${Math.max(onCard, 3).toFixed(2)}`)
      }
    }
  })

  it('⚠ keeps PLACEHOLDER a separate token, and does NOT hold it to the ink bar', () => {
    // The whole reason F7e was ~10 edits rather than ~400: `ground-400` was NAMED for placeholder
    // text and USED as muted ink in 395 of its 404 call sites, so the SMALL role moved out.
    // A placeholder is deliberately fainter than content — darkening it makes an empty field read
    // as a filled one — so it is exempt from the bar above BY DESIGN, not by oversight.
    for (const block of [lightBlockOf(), darkBlock]) {
      const ph = rgbOf(block, 'ground-placeholder')
      expect(ph).toEqual([156, 163, 175])
      // …and it must not silently become the ink stop again.
      expect(ph).not.toEqual(rgbOf(block, 'ground-400'))
    }
    // The three call sites that want it say so explicitly; nothing else may.
    const strays = walkFiles('src')
      .filter((f) => /\.(tsx?|css)$/.test(f))
      .filter((f) => /placeholder:text-ground-(?!placeholder)/.test(withoutComments(read(f))))
    expect(strays).toEqual([])
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

  it('declares a background AND an ink for EVERY control, not only `.input`', () => {
    // ⚠ THE F7c DEFECT, AND IT WAS WORSE THAN F2a's. On the officer cockpit — the one surface
    // nobody had ever opened — every text box, dropdown and textarea measured `background: white`
    // AND `color: white` in dark mode. White text in a white box: invisible, not merely faint.
    //
    // Two independent halves, neither visible in light. The BACKGROUND came from the browser,
    // because ~300 controls are written with bare utilities and never declare one — F2a fixed the
    // `.input` CLASS, and these do not use it. The INK was INHERITED from `body`, which is
    // `text-ground-900`, and `ground-900` in dark is WHITE. In light the two accidents cancel out.
    //
    // The fix is an ELEMENT rule in `@layer base`, so it covers every control written from here
    // on and any utility class still wins over it. This asserts both halves.
    const base = css.slice(css.indexOf('@layer base'))
    const block = base.slice(base.indexOf('input:not('), base.indexOf('@layer components'))
    expect(block).toMatch(/select/)
    expect(block).toMatch(/textarea/)
    expect(block).toMatch(/bg-ground-0/)
    expect(block).toMatch(/text-ground-900/)
  })

  it('keeps the stylesheet\'s OWN controls on the roles, like every component', () => {
    // ⚠ globals.css is not a component and not a surface, so no repaint sprint owned it — F2a's
    // lesson, and F7b walked straight into it again: its codemod ran over `.ts`/`.tsx` and left
    // `.btn-primary`, `.btn-secondary` and `.input` still reaching for `primary-500`.
    expect(withoutComments(css)).not.toMatch(/primary-500/)
    const btn = layers.slice(layers.indexOf('.btn-primary {'))
    expect(btn.slice(0, btn.indexOf('}'))).toMatch(/bg-brand-fill text-brand-fill-ink/)
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
  'src/components/SpecialConditions.tsx': 7,     // seven entry conditions
  'src/components/CareerPathways.tsx': 1,        // one occupation chip
  // ⚠ WAS 6 + 1. Layer 1 F6 moved the six institution types into `lib/courseBadges.ts` — the
  // course CARD described the same six independently — leaving this file only its language chip.
  'src/components/RequirementsCard.tsx': 1,      // the PISMP medium-of-instruction chip
  // Layer 1 F4 — the admin console's own category palettes.
  'src/lib/roleBadge.ts': 7,                     // seven staff roles, ONE shared copy
  'src/app/admin/students/page.tsx': 2,          // which exam a student sat: STPM / SPM
  'src/app/admin/students/[id]/page.tsx': 1,     // the STPM section's chips (no exam-type badge here)
  'src/app/admin/requests/[id]/page.tsx': 1,     // which component a request is about
  'src/app/admin/billing/page.tsx': 1,           // platform-level, against an organisation
  // Layer 1 F6 — the course guide's two, each now the ONLY description of its set.
  'src/lib/courseBadges.ts': 8,                  // eight institution types, ONE shared copy
  'src/lib/matricTracks.ts': 4,                  // four matriculation tracks, ONE shared copy
}

assertConverted('the category-palette files (F2c, F4, F6)', Object.keys(CATEGORICAL), 11)

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

  it('is a CLOSED list — another categorical file has to be a deliberate addition', () => {
    // Grown deliberately in F4 and again in F6, which is exactly what this test is for: it failed
    // on each addition and made adding them an explicit act rather than a silent one.
    expect(Object.keys(CATEGORICAL).sort()).toEqual([
      'src/app/admin/billing/page.tsx',
      'src/app/admin/requests/[id]/page.tsx',
      'src/app/admin/students/[id]/page.tsx',
      'src/app/admin/students/page.tsx',
      'src/components/CareerPathways.tsx', 'src/components/PathwayTrackCard.tsx',
      'src/components/RequirementsCard.tsx', 'src/components/SpecialConditions.tsx',
      'src/lib/courseBadges.ts', 'src/lib/matricTracks.ts',
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
    //
    // ⚠ RESPELLED AT F7e, NOT RE-DECIDED. The CLAIM — a suspended sponsor is caution at FILLED
    // weight — is unchanged and is the thing worth pinning. `bg-caution-600 text-white` was
    // measured at 3.30 in light and 1.40 in dark, so the fill became a role. Assert the role.
    expect(read('src/app/admin/sponsors/page.tsx')).toMatch(/'bg-caution-fill text-caution-fill-ink'/)
    expect(read('src/app/admin/organisation/reviewers/[id]/page.tsx')).toMatch(/declined: 'bg-caution-500'/)
    expect(read('src/app/admin/organisation/reviewers/[id]/page.tsx')).toMatch(/rejectedAfterReview: 'bg-critical-500'/)
  })
})

describe('the F5 semantic corrections the codemod could not make', () => {
  // The cockpit's ceiling (544) is GONE, not lowered: F5 converted the file, so it is covered by
  // the conversion guard above like every other admin page. A ratchet that guards a converted
  // surface is noise — the same reason F3 deleted the `src/components` one.
  // ⚠ THE VIEW, NOT THE PAGE. F7c moved the 3,500-line screen into `view.tsx` because Next forbids
  // a page module from exporting anything but its default, and the sandbox had to import it to
  // mount it at all. The route file is 22 lines now; the body did not change.
  const cockpit = 'src/app/admin/scholarship/[id]/view.tsx'

  it('paints its two Save buttons with the BRAND, like the other 38 in the console', () => {
    const src = withoutComments(read(cockpit))
    expect(src).not.toMatch(/bg-info-600[^"']*text-brand-fill-ink/)
    // ⚠ `bg-brand-fill` since F7a, not `bg-primary-600`. The stop did not change in light — the
    // ROLE did, because in dark a button and a link cannot share one number. See globals.css.
    // ⚠ AND THE PATTERN WAS TYPED BY HAND, NOT GENERATED. Its first version came out of a
    // Python heredoc and the word-boundary escape became a literal BACKSPACE byte (0x08) - F4's
    // lesson recurring through a path I had assumed was safe. It was caught only because this
    // assertion COUNTS and got 0; phrased as `not.toMatch` it would have passed over a dead regex.
    expect((src.match(/bg-brand-fill /g) ?? []).length).toBeGreaterThanOrEqual(2)
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
    // ⚠ Respelled onto the F7e fill role; the claim (FILLED, not tinted) is what is pinned.
    expect(read(cockpit)).toMatch(
      /bg-caution-fill px-1\.5 py-0\.5 text-\[11px\] font-semibold text-caution-fill-ink/)
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
    expect(src).toMatch(/bg-brand-fill text-brand-fill-ink/)
    expect(withoutComments(src)).not.toMatch(/bg-info-600/)
    // ⚠ `bg-brand-shape` since F7b, not `bg-primary-500`. A step marker is a SHAPE — an edge you
    // find, not words you read — and at the identity stop it was invisible on a dark card.
    expect(read('src/components/ProgressStepper.tsx')).toMatch(/bg-brand-shape/)
  })

  it('distinguishes "graduated" from "on track" by WEIGHT, both still positive', () => {
    // `graduated` was `indigo` — outside the vocabulary — because the set needs two good states a
    // student can tell apart. A category swatch would have been wrong (it IS a state); a second
    // tone would have lied about it. Same tone, filled instead of tinted.
    const src = read('src/app/scholarship/in-programme/page.tsx')
    // ⚠ Respelled onto the F7e fill role. The WEIGHT contrast between the two — filled vs tinted,
    // same tone — is the claim, and it is unchanged; `on_track` is a TINT and deliberately does
    // not move (a tinted panel and a filled control want opposite things when the ground inverts,
    // which is the whole reason the fill became a role).
    expect(src).toMatch(/graduated: 'bg-positive-fill text-positive-fill-ink'/)
    expect(src).toMatch(/on_track: 'bg-positive-100 text-positive-700'/)
    expect(withoutComments(src)).not.toMatch(/indigo/)
  })
})

/**
 * F6 — THE LAST SURFACE, so this one is not a file list. It is the WHOLE TREE.
 *
 * Every sprint before it named its own files, which was right while the migration was partway
 * through: `gray`/`blue`/… had to stay legal for the surfaces not yet done, so a per-surface list
 * was the only shape the guard could take. F6 finishes the job, and from here the honest assertion
 * is the strong one — nowhere under `src` carries a raw Tailwind colour, a raw hex, or an
 * arbitrary-value colour class. A new page is covered on the day it is written, with nobody having
 * to remember to add it, which is the property F7 actually needs before the switch goes on.
 *
 * ⚠ THE PER-SURFACE BLOCKS ABOVE ARE NOT REDUNDANT — DO NOT DELETE THEM. Each carries the reasoning
 * for its own sprint's judgement calls, and each fails with a message naming its surface. This one
 * fails with a list of every file in the app.
 */
const ALL_FILES = walkFiles('src').map((f) => f.split(path.sep).join('/'))

assertConverted('the WHOLE application (F6 — the migration is complete)', ALL_FILES, 240)

describe('the colour a class scan cannot see, everywhere (F6)', () => {
  // The running list of hiding places, in the order they were found: inline styles and gradients
  // (F1), the stylesheet's own @layer rules and a control with no declared background (F2a),
  // lookup tables returning class strings (F2b), arbitrary-value classes and raw hex in SVG props
  // (F3). F6 found the fifth: two quiz pages still setting `bg-[#f5f7f8]` as their whole page
  // ground — the F3 shape, in files no sprint's list had ever covered. **Assume there is one more.**
  it('has no ARBITRARY-VALUE colour class anywhere under src', () => {
    const offenders: string[] = []
    for (const f of ALL_FILES) {
      for (const m of withoutComments(read(f)).match(/-\[#[0-9a-fA-F]{3,8}\]/g) ?? []) {
        offenders.push(`${f}: ${m}`)
      }
    }
    expect(offenders).toEqual([])
  })
})

describe('the F6 semantic corrections the codemod could not make', () => {
  it('has ONE home for institution type → swatch, and three files that import it', () => {
    // The F4 role-palette shape, found twice more. `courseBadges.ts` and `RequirementsCard.tsx`
    // both described the six institution types; a student sees the first in the search grid and
    // the second on the course page, one click apart, so a drift renders the same Politeknik in
    // two colours and reads as bad data. `stpm/[id]` held a FOURTH copy, hard-coded to Universiti.
    for (const f of ['src/components/CourseCard.tsx', 'src/components/CourseHeader.tsx',
                     'src/components/RequirementsCard.tsx', 'src/app/stpm/[id]/page.tsx',
                     'src/app/pathway/matric/page.tsx', 'src/app/pathway/stpm/page.tsx']) {
      expect(read(f)).toMatch(/institutionTypeChip/)
      // …and none of them may re-declare a swatch of its own.
      expect(withoutComments(read(f))).not.toMatch(/'bg-category-\d-surface text-category-\d-ink'/)
    }
  })

  it('keeps the STPM subject vocabulary and the matric tracks in one file each', () => {
    // Both were declared twice, byte-identical, in `course/[id]` and the pathway page — the two
    // pages a student moves between while comparing. Same bug as above, found by grepping for
    // `Record<…, colour>` rather than by reading, which is why that grep is on the checklist.
    for (const f of ['src/app/course/[id]/page.tsx', 'src/app/pathway/stpm/page.tsx']) {
      expect(read(f)).toMatch(/from '@\/lib\/stpmSubjects'/)
      expect(withoutComments(read(f))).not.toMatch(/const SUBJECT_NAMES/)
    }
    for (const f of ['src/app/course/[id]/page.tsx', 'src/app/pathway/matric/page.tsx']) {
      expect(read(f)).toMatch(/from '@\/lib\/matricTracks'/)
      expect(withoutComments(read(f))).not.toMatch(/const TRACK_COLOURS/)
    }
  })

  it('draws the subject and level chips with ONE class each, not a palette', () => {
    // ⚠ THIS IS THE SPRINT'S LOAD-BEARING DECISION, AND IT IS A REFUSAL TO WIDEN THE FAMILY.
    // 17 subject codes wanted 16 hues and the type+level pair wanted 13; the family has 8, and the
    // eight avoid green/blue/amber/red so a category is never read as a status. Sixteen hues that
    // dodge those four AND separate in dark mode do not exist. Both sets went neutral instead,
    // which cost nothing: every subject chip renders beside its own full name, every level chip
    // says "Diploma", and an unrecognised level had ALWAYS been grey.
    // If a later sprint wants these coloured, the change is to `--category-*`, not to these files.
    expect(read('src/lib/stpmSubjects.ts')).toMatch(/SUBJECT_CHIP = 'bg-ground-100 text-ground-700'/)
    expect(read('src/lib/courseBadges.ts')).toMatch(/LEVEL_CHIP = 'bg-ground-100 text-ground-700'/)
    // Neither may quietly become a lookup table again.
    expect(withoutComments(read('src/lib/stpmSubjects.ts'))).not.toMatch(/SUBJECT_COLORS/)
    expect(withoutComments(read('src/lib/courseBadges.ts'))).not.toMatch(/LEVEL_COLORS/)
  })

  it('paints the search page\'s qualification toggles with the BRAND', () => {
    // Fifth sprint running that the codemod called a control the user ACTS on "information". Worse
    // here than usual: SPM was `bg-blue-600` and STPM `bg-purple-600`, so the SELECTED state of two
    // buttons in one segmented control was two different colours, neither of them the tenant's.
    const src = withoutComments(read('src/app/search/page.tsx'))
    expect(src.match(/bg-brand-fill text-brand-fill-ink/g)?.length).toBe(2)
    expect(src).not.toMatch(/bg-info-600 text-white/)
  })

  it('has no filled control left on a TONE across the whole app', () => {
    // The F4 guard, widened from the console to everywhere now that everywhere is converted.
    // ⚠ ESCAPES WRITTEN BY HAND. F4's version of this line was script-generated and its \b became
    // a literal backspace byte: it compiled, matched nothing, and passed forever.
    // `positive` and `critical` are NOT included — an Approve button and a Delete button assert
    // their outcome, and F4 ruled on exactly that. This is about `info`, which asserts nothing.
    const offenders: string[] = []
    for (const f of ALL_FILES) {
      if (!f.endsWith('.tsx')) continue
      for (const line of withoutComments(read(f)).split('\n')) {
        if (/\btext-white\b/.test(line) && /\bbg-info-[567]00\b/.test(line)) {
          offenders.push(`${f}: ${line.trim()}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })
})
