/**
 * Country dial codes for the sponsor phone field (sponsors may be overseas).
 * Data is name + ISO-3166 alpha-2 + E.164 dial code; the flag emoji is DERIVED
 * from the ISO code (no need to hand-maintain 100 emojis). Pure/renderer-free so
 * it's unit-testable in node-env jest.
 */
export interface Country {
  name: string
  iso2: string
  dial: string   // digits only, no '+'
}

/** Malaysia first (the common case + default), then alphabetical. */
export const COUNTRIES: Country[] = [
  { name: 'Malaysia', iso2: 'MY', dial: '60' },
  { name: 'Afghanistan', iso2: 'AF', dial: '93' },
  { name: 'Albania', iso2: 'AL', dial: '355' },
  { name: 'Algeria', iso2: 'DZ', dial: '213' },
  { name: 'Argentina', iso2: 'AR', dial: '54' },
  { name: 'Australia', iso2: 'AU', dial: '61' },
  { name: 'Austria', iso2: 'AT', dial: '43' },
  { name: 'Bahrain', iso2: 'BH', dial: '973' },
  { name: 'Bangladesh', iso2: 'BD', dial: '880' },
  { name: 'Belgium', iso2: 'BE', dial: '32' },
  { name: 'Bhutan', iso2: 'BT', dial: '975' },
  { name: 'Brazil', iso2: 'BR', dial: '55' },
  { name: 'Brunei', iso2: 'BN', dial: '673' },
  { name: 'Cambodia', iso2: 'KH', dial: '855' },
  { name: 'Canada', iso2: 'CA', dial: '1' },
  { name: 'Chile', iso2: 'CL', dial: '56' },
  { name: 'China', iso2: 'CN', dial: '86' },
  { name: 'Colombia', iso2: 'CO', dial: '57' },
  { name: 'Denmark', iso2: 'DK', dial: '45' },
  { name: 'Egypt', iso2: 'EG', dial: '20' },
  { name: 'Fiji', iso2: 'FJ', dial: '679' },
  { name: 'Finland', iso2: 'FI', dial: '358' },
  { name: 'France', iso2: 'FR', dial: '33' },
  { name: 'Germany', iso2: 'DE', dial: '49' },
  { name: 'Ghana', iso2: 'GH', dial: '233' },
  { name: 'Greece', iso2: 'GR', dial: '30' },
  { name: 'Hong Kong', iso2: 'HK', dial: '852' },
  { name: 'Hungary', iso2: 'HU', dial: '36' },
  { name: 'India', iso2: 'IN', dial: '91' },
  { name: 'Indonesia', iso2: 'ID', dial: '62' },
  { name: 'Iran', iso2: 'IR', dial: '98' },
  { name: 'Iraq', iso2: 'IQ', dial: '964' },
  { name: 'Ireland', iso2: 'IE', dial: '353' },
  { name: 'Israel', iso2: 'IL', dial: '972' },
  { name: 'Italy', iso2: 'IT', dial: '39' },
  { name: 'Japan', iso2: 'JP', dial: '81' },
  { name: 'Jordan', iso2: 'JO', dial: '962' },
  { name: 'Kazakhstan', iso2: 'KZ', dial: '7' },
  { name: 'Kenya', iso2: 'KE', dial: '254' },
  { name: 'Kuwait', iso2: 'KW', dial: '965' },
  { name: 'Laos', iso2: 'LA', dial: '856' },
  { name: 'Lebanon', iso2: 'LB', dial: '961' },
  { name: 'Macau', iso2: 'MO', dial: '853' },
  { name: 'Maldives', iso2: 'MV', dial: '960' },
  { name: 'Mauritius', iso2: 'MU', dial: '230' },
  { name: 'Mexico', iso2: 'MX', dial: '52' },
  { name: 'Morocco', iso2: 'MA', dial: '212' },
  { name: 'Myanmar', iso2: 'MM', dial: '95' },
  { name: 'Nepal', iso2: 'NP', dial: '977' },
  { name: 'Netherlands', iso2: 'NL', dial: '31' },
  { name: 'New Zealand', iso2: 'NZ', dial: '64' },
  { name: 'Nigeria', iso2: 'NG', dial: '234' },
  { name: 'Norway', iso2: 'NO', dial: '47' },
  { name: 'Oman', iso2: 'OM', dial: '968' },
  { name: 'Pakistan', iso2: 'PK', dial: '92' },
  { name: 'Philippines', iso2: 'PH', dial: '63' },
  { name: 'Poland', iso2: 'PL', dial: '48' },
  { name: 'Portugal', iso2: 'PT', dial: '351' },
  { name: 'Qatar', iso2: 'QA', dial: '974' },
  { name: 'Romania', iso2: 'RO', dial: '40' },
  { name: 'Russia', iso2: 'RU', dial: '7' },
  { name: 'Saudi Arabia', iso2: 'SA', dial: '966' },
  { name: 'Singapore', iso2: 'SG', dial: '65' },
  { name: 'South Africa', iso2: 'ZA', dial: '27' },
  { name: 'South Korea', iso2: 'KR', dial: '82' },
  { name: 'Spain', iso2: 'ES', dial: '34' },
  { name: 'Sri Lanka', iso2: 'LK', dial: '94' },
  { name: 'Sweden', iso2: 'SE', dial: '46' },
  { name: 'Switzerland', iso2: 'CH', dial: '41' },
  { name: 'Taiwan', iso2: 'TW', dial: '886' },
  { name: 'Thailand', iso2: 'TH', dial: '66' },
  { name: 'Turkey', iso2: 'TR', dial: '90' },
  { name: 'Uganda', iso2: 'UG', dial: '256' },
  { name: 'Ukraine', iso2: 'UA', dial: '380' },
  { name: 'United Arab Emirates', iso2: 'AE', dial: '971' },
  { name: 'United Kingdom', iso2: 'GB', dial: '44' },
  { name: 'United States', iso2: 'US', dial: '1' },
  { name: 'Vietnam', iso2: 'VN', dial: '84' },
  { name: 'Yemen', iso2: 'YE', dial: '967' },
]

export const DEFAULT_COUNTRY_ISO = 'MY'

/** Flag emoji from an ISO-3166 alpha-2 code (regional-indicator letters). */
export function flagOf(iso2: string): string {
  const s = (iso2 || '').toUpperCase()
  if (!/^[A-Z]{2}$/.test(s)) return '🏳️'
  return s.replace(/./g, (c) => String.fromCodePoint(127397 + c.charCodeAt(0)))
}

export function countryByIso(iso2: string): Country | undefined {
  const s = (iso2 || '').toUpperCase()
  return COUNTRIES.find((c) => c.iso2 === s)
}

/** Longest dial-prefix match for a run of digits (e.g. "60123…" → Malaysia).
 *  Dials tie on '1'/'7' (US↔CA, RU↔KZ) — the first listed wins, which is fine
 *  for pre-filling an existing number's country flag. */
export function countryByDial(digits: string): Country | undefined {
  const d = (digits || '').replace(/\D/g, '')
  let best: Country | undefined
  for (const c of COUNTRIES) {
    if (d.startsWith(c.dial) && (!best || c.dial.length > best.dial.length)) best = c
  }
  return best
}
