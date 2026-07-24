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

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function mix(channel: number, target: number, t: number): number {
  return Math.round(channel + (target - channel) * t)
}

/** Compute a 50–900 tint/shade ramp from a base hex (treated as the 500 step), returning each
 *  step as a space-separated RGB triplet (the CSS-var channel form). Tenant-only — the platform
 *  ramp is the exact seeded hexes baked into `globals.css`, so this never runs for BrightPath. */
export function brandRamp(hex: string): Record<number, string> {
  const [r, g, b] = hexToRgb(hex)
  const light = (t: number) => `${mix(r, 255, t)} ${mix(g, 255, t)} ${mix(b, 255, t)}`
  const dark = (t: number) => `${mix(r, 0, t)} ${mix(g, 0, t)} ${mix(b, 0, t)}`
  return {
    50: light(0.95),
    100: light(0.85),
    200: light(0.7),
    300: light(0.5),
    400: light(0.25),
    500: `${r} ${g} ${b}`,
    600: dark(0.15),
    700: dark(0.3),
    800: dark(0.45),
    900: dark(0.6),
  }
}
