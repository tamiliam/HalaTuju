/**
 * Per-org branding — the frontend seam (platform Sprint 6, decision D2).
 *
 * This is the ONE sanctioned home for the app's brand LITERALS ("BrightPath Bursary",
 * "Cikgu Gopal", "halatuju.xyz", the platform brand colour + logo). The brand-guard test
 * (`brand-guard.test.ts`) allows those literals ONLY in this module; anywhere else in
 * `src/**` (message values or code) is a leak.
 *
 * Design (byte-identity contract):
 *  - `PLATFORM` holds today's FE literals verbatim. BrightPath (env unset / 'brightpath')
 *    renders from `PLATFORM` and NEVER fetches — zero change, zero flash.
 *  - `resolveBranding(config)` maps the public /branding/<code>/ payload to a resolved
 *    shape, with an ''-falls-through fallback (an empty tenant column → the platform value).
 *  - `interpolateMessage()` is the `{var}` engine extracted from `i18n.tsx`; a FUNCTION
 *    replacer closes the `$`-in-replacement hazard the old `String.replace(str)` form had.
 *  - The five `AUTO_TOKENS` are the branding params `t()` auto-injects beneath explicit
 *    call-site params, so every message string is tenancy-safe without per-call threading.
 */

export type Locale = 'en' | 'ms' | 'ta'

export type ThemeMode = 'light' | 'dark'

/** A tenant's STORED colour tokens, one block per mode: `{ 'brand-50': '250 244 251', … }`.
 *  Values are the space-separated RGB triplets the CSS custom properties take, so painting is a
 *  straight `setProperty('--brand-50', triplet)` with no conversion. (Layer 1 A1.) */
export type ThemeTokens = Record<ThemeMode, Record<string, string>>

/** What a tenant may tint. Mirrors `TENANT_FAMILIES` in `apps/courses/theme_tokens.py`. */
const TENANT_FAMILIES = ['brand']

const TOKEN_NAME = /^([a-z]+)-([0-9]+)$/
const TRIPLET = /^[0-9]{1,3} [0-9]{1,3} [0-9]{1,3}$/

/**
 * Keep only the tokens this app is allowed to paint; return null rather than half a theme.
 *
 * The server fences on write AND filters on read, so this is the third copy of one rule — and it
 * earns its place, because it is the only one that runs on the bytes the BROWSER actually received.
 * A tone repainted by a tenant would not change how the product looks so much as what it MEANS:
 * red stops meaning "this is broken". Cheap to keep honest, so it is kept honest here too.
 */
export function applicableTokens(raw: unknown): ThemeTokens | null {
  if (!raw || typeof raw !== 'object') return null
  const out = {} as ThemeTokens
  for (const mode of ['light', 'dark'] as ThemeMode[]) {
    const block = (raw as Record<string, unknown>)[mode]
    if (!block || typeof block !== 'object') return null
    const kept: Record<string, string> = {}
    for (const [name, value] of Object.entries(block as Record<string, unknown>)) {
      const parts = name.match(TOKEN_NAME)
      if (!parts || !TENANT_FAMILIES.includes(parts[1])) continue
      if (typeof value !== 'string' || !TRIPLET.test(value)) continue
      kept[name] = value
    }
    if (Object.keys(kept).length === 0) return null
    out[mode] = kept
  }
  return out
}

/** The raw shape of the public GET /api/v1/branding/<code>/ payload (all optional — a total,
 *  never-raises endpoint). Per-language groups may be partial; '' means "fall through". */
export interface BrandingConfig {
  programme_name?: Partial<Record<Locale, string>> | null
  persona_name?: Partial<Record<Locale, string>> | null
  org_short_name?: string | null
  brand_colour?: string | null
  logo_url?: string | null
  email_support?: string | null
  sponsor_email?: string | null
  frontend_domain?: string | null
  /** The tenant's stored colour tokens, or null = "paint the stylesheet you already have". */
  theme?: unknown
}

export interface ResolvedBranding {
  programmeName: Record<Locale, string>
  personaName: Record<Locale, string>
  orgShortName: string
  brandColour: string
  logoUrl: string
  logoAlt: string
  emailSupport: string
  sponsorEmail: string
  frontendDomain: string
  /** The APPROVED shades, when this tenant has stored some. null → derive from `brandColour`
   *  exactly as before A1, which is what keeps the platform and un-themed tenants unchanged. */
  theme: ThemeTokens | null
}

/** Today's FE brand constants, verbatim — the one sanctioned literal home (guard-allowlisted).
 *  NOTE: the persona renders in LATIN "Cikgu Gopal" in ALL THREE locales in the web app (the
 *  Tamil SCRIPT `சிக்கு கோபால்` is an EMAIL-body-only form on the backend seam); keeping Latin
 *  here is what makes the ta coach strings render byte-identically. `logoAlt` is the platform
 *  PRODUCT name "HalaTuju" (kept everywhere as platform identity), not the programme name. */
export const PLATFORM: ResolvedBranding = {
  programmeName: { en: 'BrightPath Bursary', ms: 'Bursari BrightPath', ta: 'BrightPath Bursary' },
  personaName: { en: 'Cikgu Gopal', ms: 'Cikgu Gopal', ta: 'Cikgu Gopal' },
  orgShortName: 'BrightPath',
  brandColour: '#137fec',
  logoUrl: '/logo-icon.png',
  logoAlt: 'HalaTuju',
  emailSupport: 'help@halatuju.xyz',
  sponsorEmail: 'sponsor@halatuju.xyz',
  frontendDomain: 'halatuju.xyz',
  // The platform stores NO token set, deliberately: the light ramp in `globals.css` is the seeded
  // brand hexes rather than `brandRamp()`'s output, so a derived set would move BrightPath's own
  // colours by a channel. null keeps the stylesheet in charge. (Layer 1 A1.)
  theme: null,
}

/** The five branding params `t()` auto-injects into every message render (beneath explicit
 *  params). A message value may reference any of these and it resolves per-tenant for free. */
export const AUTO_TOKENS = [
  'programmeName',
  'orgShortName',
  'personaName',
  'supportEmail',
  'displayDomain',
] as const

const LOCALES: Locale[] = ['en', 'ms', 'ta']

function keep(value: string | null | undefined, fallback: string): string {
  return value && value.trim() ? value : fallback
}

function resolveLang(
  group: Partial<Record<Locale, string>> | null | undefined,
  fallback: Record<Locale, string>,
): Record<Locale, string> {
  const out = {} as Record<Locale, string>
  for (const loc of LOCALES) out[loc] = keep(group ? group[loc] : undefined, fallback[loc])
  return out
}

/** Resolve a raw branding config (or null → the platform) into the shape the app renders from.
 *  Every field falls through to the PLATFORM default when the tenant column is empty ('' or
 *  missing), so a partially-configured tenant never renders a blank. */
export function resolveBranding(config: BrandingConfig | null | undefined): ResolvedBranding {
  if (!config) return PLATFORM
  const orgShort = keep(config.org_short_name, PLATFORM.orgShortName)
  return {
    programmeName: resolveLang(config.programme_name, PLATFORM.programmeName),
    personaName: resolveLang(config.persona_name, PLATFORM.personaName),
    orgShortName: orgShort,
    brandColour: keep(config.brand_colour, PLATFORM.brandColour),
    logoUrl: keep(config.logo_url, PLATFORM.logoUrl),
    // A tenant's logo alt = its short name (its identity). The platform keeps "HalaTuju"
    // via the early return above, so BrightPath's alt is byte-identical to today.
    logoAlt: orgShort,
    emailSupport: keep(config.email_support, PLATFORM.emailSupport),
    sponsorEmail: keep(config.sponsor_email, PLATFORM.sponsorEmail),
    frontendDomain: keep(config.frontend_domain, PLATFORM.frontendDomain),
    theme: applicableTokens(config.theme),
  }
}

/** The five AUTO_TOKENS resolved for one locale — the param map `t()` merges beneath the
 *  call-site params (explicit params always win). */
export function brandingParams(branding: ResolvedBranding, locale: Locale): Record<string, string> {
  return {
    programmeName: branding.programmeName[locale],
    orgShortName: branding.orgShortName,
    personaName: branding.personaName[locale],
    supportEmail: branding.emailSupport,
    displayDomain: branding.frontendDomain,
  }
}

/** Substitute `{var}` placeholders in a message string. Mirrors the old `i18n.tsx` engine
 *  exactly (per-key global replace, unknown placeholders left untouched) but uses a FUNCTION
 *  replacer so a `$` inside a replacement value is inserted literally (the old string form
 *  treated `$&`/`$1`/`$$` specially). A `'{'`-absent fast path skips the work entirely. */
export function interpolateMessage(value: string, params?: Record<string, string>): string {
  if (!params || value.indexOf('{') === -1) return value
  let out = value
  for (const [k, v] of Object.entries(params)) {
    out = out.replace(new RegExp(`\\{${k}\\}`, 'g'), () => v)
  }
  return out
}

// ── Tenant colour ramp (tenant-only; BrightPath uses the verbatim literal ramp in globals.css) ──

type Rgb = [number, number, number]

/** `--ground-50` in dark mode — the page a tinted brand panel actually sits on. `theme.test.ts`
 *  reads this AND `globals.css` and refuses to let the two drift apart. */
const DARK_GROUND: Rgb = [17, 24, 39]

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function mix(channel: number, target: number, t: number): number {
  return Math.round(channel + (target - channel) * t)
}

/**
 * Compute a 50–900 ramp from a base hex (the 500 step), each step a space-separated RGB triplet.
 *
 * ── WHY THIS TAKES A THEME (Layer 1 F3b, owner direction 2026-08-31) ──
 * The ramp is derived by mixing the brand colour toward two ends. In light mode those ends are
 * white (for the tints) and black (for the shades), which is right for a white page. In dark mode
 * it is exactly backwards: `50`–`200` are 95–70% WHITE, so a panel painted with one is a glaring
 * pale patch on a dark page, and `800`–`900` are 45–60% BLACK, so text in one is near invisible.
 * F3 measured 101 uses of the pale stops as SURFACES across 40 files.
 *
 * The fix cannot be a second, hand-picked palette: a tenant supplies ONE colour at runtime, so any
 * dark treatment has to be DERIVED from whatever they set. So the two ends swap — the tints mix
 * toward the dark page, the shades mix toward white.
 *
 * ⚠ `500` IS THE SAME VALUE IN BOTH MODES, and that is the whole of the owner's ruling. The rule
 * (2026-07-29) is that a theme may never change WHOSE product you are looking at. The identity
 * stop IS the brand; the other nine are furniture derived from it, and re-aiming furniture at the
 * surface it actually sits on does not change the identity. `theme.test.ts` pins `500`
 * byte-for-byte across the two modes — a stricter and more honest test than "the dark block
 * contains no `--brand-`" ever was.
 */
export function brandRamp(hex: string, theme: 'light' | 'dark' = 'light'): Record<number, string> {
  const [r, g, b] = hexToRgb(hex)
  // The two ends the ramp is pulled toward. In dark they are the page ground and white — the same
  // pair swapped, so a tint stays a tint RELATIVE TO ITS BACKGROUND rather than absolutely.
  const [toTint, toShade]: [Rgb, Rgb] = theme === 'dark'
    ? [DARK_GROUND, [255, 255, 255]]
    : [[255, 255, 255], [0, 0, 0]]
  const towards = ([tr, tg, tb]: Rgb, t: number) =>
    `${mix(r, tr, t)} ${mix(g, tg, t)} ${mix(b, tb, t)}`
  return {
    50: towards(toTint, 0.95),
    100: towards(toTint, 0.85),
    200: towards(toTint, 0.7),
    300: towards(toTint, 0.5),
    400: towards(toTint, 0.25),
    500: `${r} ${g} ${b}`,
    600: towards(toShade, 0.15),
    700: towards(toShade, 0.3),
    800: towards(toShade, 0.45),
    900: towards(toShade, 0.6),
  }
}
