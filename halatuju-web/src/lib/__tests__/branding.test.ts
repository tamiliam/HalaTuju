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
})
