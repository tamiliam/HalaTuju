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

describe('the sponsor portal is fully converted', () => {
  // F1's surface. This is the guard that stops raw colour creeping back into a surface already
  // migrated — Tailwind's own `gray`/`blue`/… stay available for the unmigrated ones, so the
  // absence of the utility cannot be the guard.
  const files: string[] = []
  const walk = (dir: string) => {
    for (const e of fs.readdirSync(path.join(process.cwd(), dir), { withFileTypes: true })) {
      if (e.name === '__tests__') continue
      const rel = path.join(dir, e.name)
      if (e.isDirectory()) walk(rel)
      else if (/\.tsx?$/.test(e.name) && !/\.test\./.test(e.name)) files.push(rel)
    }
  }
  walk('src/app/sponsor')
  walk('src/components/sponsors')

  const RAW = /\b(?:bg|text|border|ring|divide|from|to|via|placeholder)-(?:gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/

  it('mounts enough files for this test to mean something', () => {
    expect(files.length).toBeGreaterThan(15)
  })

  it('has no raw Tailwind colour left anywhere in it', () => {
    const offenders = files
      .map((f) => [f, read(f).match(new RegExp(RAW, 'g'))] as const)
      .filter(([, m]) => m)
      .map(([f, m]) => `${f}: ${Array.from(new Set(m!)).join(', ')}`)
    expect(offenders).toEqual([])
  })

  it('keeps text-white literal — it must NOT invert with the ground', () => {
    // 214 uses across the product, nearly all on a coloured or dark surface: a button label, a
    // filled badge. Mapped onto --ground-0 they would turn black in dark mode. The codemod converts
    // BACKGROUND white only, and this asserts the distinction survived on this surface.
    const withWhiteText = files.filter((f) => /\btext-white\b/.test(read(f)))
    expect(withWhiteText.length).toBeGreaterThan(0)
    for (const f of withWhiteText) expect(read(f)).not.toMatch(/\btext-ground-0\b/)
  })
})
