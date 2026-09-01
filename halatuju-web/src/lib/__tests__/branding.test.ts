/**
 * Phase 1 — the FE branding seam (pure). Pins the platform literals, the ''-falls-through
 * resolution, the AUTO_TOKEN param map, the `{var}` engine (incl. the `$`-hazard fix and the
 * fast path), and the tenant colour ramp. No app code is exercised — this locks the seam's
 * contract before any provider / t() / message change lands.
 */
import {
  PLATFORM,
  AUTO_TOKENS,
  resolveBranding,
  brandingParams,
  interpolateMessage,
  brandRamp,
  applicableTokens,
  type BrandingConfig,
} from '@/lib/branding'

describe('PLATFORM literals (today, verbatim)', () => {
  it('holds the current brand constants', () => {
    expect(PLATFORM.programmeName).toEqual({
      en: 'BrightPath Bursary',
      ms: 'Bursari BrightPath',
      ta: 'BrightPath Bursary',
    })
    // Persona is LATIN in all three locales in the web app (Tamil script is email-only).
    expect(PLATFORM.personaName).toEqual({
      en: 'Cikgu Gopal',
      ms: 'Cikgu Gopal',
      ta: 'Cikgu Gopal',
    })
    expect(PLATFORM.orgShortName).toBe('BrightPath')
    expect(PLATFORM.brandColour).toBe('#137fec')
    expect(PLATFORM.logoUrl).toBe('/logo-icon.png')
    expect(PLATFORM.logoAlt).toBe('HalaTuju')
    expect(PLATFORM.emailSupport).toBe('help@halatuju.xyz')
    expect(PLATFORM.sponsorEmail).toBe('sponsor@halatuju.xyz')
    expect(PLATFORM.frontendDomain).toBe('halatuju.xyz')
  })

  it('AUTO_TOKENS is exactly the five injected params', () => {
    expect([...AUTO_TOKENS]).toEqual([
      'programmeName', 'orgShortName', 'personaName', 'supportEmail', 'displayDomain',
    ])
  })
})

describe('resolveBranding', () => {
  it('null / undefined → the PLATFORM object itself', () => {
    expect(resolveBranding(null)).toBe(PLATFORM)
    expect(resolveBranding(undefined)).toBe(PLATFORM)
  })

  it('a full tenant config maps to the resolved shape', () => {
    const cfg: BrandingConfig = {
      programme_name: { en: 'Inspire Grant', ms: 'Geran Inspire', ta: 'இன்ஸ்பயர்' },
      persona_name: { en: 'Cikgu Aishah', ms: 'Cikgu Aishah', ta: 'Cikgu Aishah' },
      org_short_name: 'Inspire',
      brand_colour: '#a21caf',
      logo_url: 'https://cdn.inspire.example/logo.png',
      email_support: 'help@inspire.example',
      sponsor_email: 'sponsor@inspire.example',
      frontend_domain: 'inspire.example',
    }
    const b = resolveBranding(cfg)
    expect(b.programmeName.ms).toBe('Geran Inspire')
    expect(b.orgShortName).toBe('Inspire')
    expect(b.logoAlt).toBe('Inspire') // tenant alt = its short name
    expect(b.brandColour).toBe('#a21caf')
    expect(b.frontendDomain).toBe('inspire.example')
  })

  it("'' and missing columns fall through to the platform default (per-language)", () => {
    const b = resolveBranding({
      programme_name: { en: 'Inspire Grant', ms: '', ta: '   ' }, // ms empty, ta whitespace
      org_short_name: '',
      brand_colour: null,
    })
    expect(b.programmeName.en).toBe('Inspire Grant')
    expect(b.programmeName.ms).toBe('Bursari BrightPath') // fell through
    expect(b.programmeName.ta).toBe('BrightPath Bursary') // whitespace → fell through
    expect(b.orgShortName).toBe('BrightPath')
    expect(b.brandColour).toBe('#137fec')
    expect(b.emailSupport).toBe('help@halatuju.xyz') // absent → platform
  })
})

describe('brandingParams', () => {
  it('resolves the five tokens for a locale from the platform', () => {
    expect(brandingParams(PLATFORM, 'ms')).toEqual({
      programmeName: 'Bursari BrightPath',
      orgShortName: 'BrightPath',
      personaName: 'Cikgu Gopal',
      supportEmail: 'help@halatuju.xyz',
      displayDomain: 'halatuju.xyz',
    })
  })
})

describe('interpolateMessage', () => {
  it('substitutes every {var} globally', () => {
    expect(interpolateMessage('{a} and {a} then {b}', { a: 'X', b: 'Y' })).toBe('X and X then Y')
  })

  it('leaves unknown placeholders untouched', () => {
    expect(interpolateMessage('{known} {unknown}', { known: 'K' })).toBe('K {unknown}')
  })

  it("inserts a '$' in the replacement value literally (the hazard the function replacer closes)", () => {
    // The old String.replace(str) form would treat $& / $1 / $$ specially and corrupt this.
    expect(interpolateMessage('Pay {amt}', { amt: 'RM$50' })).toBe('Pay RM$50')
    expect(interpolateMessage('{x}', { x: '$&' })).toBe('$&')
    expect(interpolateMessage('{x}', { x: '$$' })).toBe('$$')
  })

  it("fast path: a '{'-absent string is returned unchanged", () => {
    const s = 'no placeholders here'
    expect(interpolateMessage(s, { a: 'X' })).toBe(s)
  })

  it('no params → identity', () => {
    expect(interpolateMessage('{a}')).toBe('{a}')
  })
})

describe('brandRamp (tenant-only)', () => {
  it('returns 10 space-separated RGB triplets with 500 = the exact base', () => {
    const ramp = brandRamp('#137fec') // 19 127 236
    expect(ramp[500]).toBe('19 127 236')
    expect(Object.keys(ramp)).toHaveLength(10)
    for (const step of [50, 100, 200, 300, 400, 600, 700, 800, 900]) {
      expect(ramp[step]).toMatch(/^\d{1,3} \d{1,3} \d{1,3}$/)
    }
  })

  /**
   * ⚠ THE CROSS-LANGUAGE PIN (Layer 1 A1).
   *
   * `apps/courses/theme_tokens.py` derives a tenant's shades at SAVE time; this function derives
   * them in the browser for a tenant that has not stored a set yet. Two implementations of one sum
   * is a drift risk with a nasty symptom — a tenant's colours would shift by a channel the moment
   * a theme row was created, which nobody would read as a bug.
   *
   * So both sides assert THE SAME fixture for the same input. If either drifts, that language's
   * own suite fails. The Python copy is `GOLDEN` in `apps/courses/tests/test_organisation_theme.py`
   * and the values are hand-verified at the corners.
   */
  const GOLDEN = {
    light: {
      50: '250 244 251', 100: '241 221 243', 200: '227 187 231', 300: '209 142 215',
      400: '185 85 195', 500: '162 28 175', 600: '138 24 149', 700: '113 20 123',
      800: '89 15 96', 900: '65 11 70',
    },
    dark: {
      50: '24 24 46', 100: '39 25 59', 200: '61 25 80', 300: '90 26 107',
      400: '126 27 141', 500: '162 28 175', 600: '176 62 187', 700: '190 96 199',
      800: '204 130 211', 900: '218 164 223',
    },
  } as const

  it('agrees byte-for-byte with the backend derivation', () => {
    expect(brandRamp('#a21caf', 'light')).toEqual(GOLDEN.light)
    expect(brandRamp('#a21caf', 'dark')).toEqual(GOLDEN.dark)
  })
})

describe('applicableTokens — the fence, on the bytes the browser received', () => {
  const good = {
    light: { 'brand-50': '250 244 251', 'brand-500': '162 28 175' },
    dark: { 'brand-50': '24 24 46', 'brand-500': '162 28 175' },
  }

  it('keeps a tenant brand token', () => {
    expect(applicableTokens(good)).toEqual(good)
  })

  it('DROPS a platform tone, whatever the server sent', () => {
    // The durable rule: red means "this is broken". A tenant may not redefine a meaning.
    for (const family of ['positive', 'info', 'caution', 'critical', 'category', 'ground']) {
      const smuggled = {
        light: { ...good.light, [`${family}-500`]: '0 255 0' },
        dark: { ...good.dark, [`${family}-500`]: '0 255 0' },
      }
      const out = applicableTokens(smuggled)!
      expect(out.light[`${family}-500`]).toBeUndefined()
      expect(out.light['brand-500']).toBe('162 28 175')
    }
  })

  it('drops a malformed value rather than painting it', () => {
    const out = applicableTokens({
      light: { ...good.light, 'brand-100': '#a21caf' },
      dark: good.dark,
    })!
    expect(out.light['brand-100']).toBeUndefined()
    expect(out.light['brand-50']).toBe('250 244 251')
  })

  it('returns null rather than half a theme', () => {
    expect(applicableTokens(null)).toBeNull()
    expect(applicableTokens(undefined)).toBeNull()
    expect(applicableTokens('blue')).toBeNull()
    expect(applicableTokens({ light: good.light })).toBeNull() // no dark block
    expect(applicableTokens({ light: {}, dark: good.dark })).toBeNull()
    expect(applicableTokens({ light: { 'critical-500': '1 2 3' }, dark: good.dark })).toBeNull()
  })
})

describe('resolveBranding carries the theme', () => {
  it('the platform has none — the stylesheet stays in charge', () => {
    expect(PLATFORM.theme).toBeNull()
    expect(resolveBranding({}).theme).toBeNull()
  })

  it('a tenant set survives resolution', () => {
    const cfg: BrandingConfig = {
      theme: {
        light: { 'brand-500': '162 28 175' },
        dark: { 'brand-500': '162 28 175' },
      },
    }
    expect(resolveBranding(cfg).theme!.light['brand-500']).toBe('162 28 175')
  })
})
