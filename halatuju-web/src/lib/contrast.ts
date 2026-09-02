/**
 * The contrast check, in the browser — Layer 1 A2.
 *
 * ⚠ THIS IS NOT THE GATE. `apps/courses/contrast.py` is the gate: it refuses the save, and it runs
 * whatever the browser did. This module exists so the person choosing a colour sees the answer as
 * they type instead of after a round trip — a courtesy, and a courtesy that must agree with the
 * server or it is worse than nothing.
 *
 * The pair keys are the SERVER'S keys, so a `400 unreadable` naming `filled_button` maps straight
 * onto the same row the screen already drew. Two lists that must line up, and the sensible place to
 * make them line up is a shared vocabulary rather than a translation table.
 *
 * The maths is WCAG 2.1's relative luminance, mirrored from the Python. Both sides assert the same
 * golden fixture (`contrast.test.ts` here, `test_contrast.py` there) so a drift fails loudly on the
 * side that drifted.
 */
import { brandRamp, BRAND_ROLE } from '@/lib/branding'

export type Rgb = [number, number, number]

/** WCAG AA for normal-size text. Every pair below carries words except `ui_shape`. */
export const AA_TEXT = 4.5

/** WCAG AA for non-text: a shape whose boundary must be discernible, not read. */
export const AA_NON_TEXT = 3.0

/** The platform surfaces, per mode. `white` and `ground-0` are separate on purpose — `text-white`
 *  is a literal in this codebase and deliberately never became `text-ground-0`. In light they are
 *  the same colour; in dark they are nothing like each other, which is why the table is per mode.
 *  Mirrors `PLATFORM_SURFACES` in `apps/courses/contrast.py`. */
const SURFACES: Record<ThemeMode, Record<string, Rgb>> = {
  light: { white: [255, 255, 255], 'ground-0': [255, 255, 255], 'ground-50': [249, 250, 251] },
  dark: { white: [255, 255, 255], 'ground-0': [31, 41, 55], 'ground-50': [17, 24, 39] },
}

export type ThemeMode = 'light' | 'dark'

export interface Pair {
  /** The server's key for this pair. Do not rename one side only. */
  key: string
  /** A ramp step, a platform surface name, or a `fill*` ROLE resolved per mode. */
  ink: number | string
  surface: number | string
  min: number
}

/**
 * The pairs the product renders, counted in `src/**` rather than imagined.
 *
 * `ui_shape` carries a different bar because the brand's shape stop no longer carries text: A2 moved 52
 * filled controls off it onto `-600`, leaving dots, progress bars, toggles and aria-hidden icon
 * circles. Holding a shape to the text bar is what made the gate refuse the platform's own colour.
 *
 * `filled_button_visible` is F7a's, and it is the pair that stops the obvious wrong fix: moving the
 * button down the ramp so white text reads in dark ALSO drops it to 2.52 against its own card. A
 * control has to be findable as well as readable, so both bars are held at once.
 */
export const PAIRS: Pair[] = [
  { key: 'filled_button', ink: 'fill-ink', surface: 'fill', min: AA_TEXT },
  { key: 'filled_button_hover', ink: 'fill-ink', surface: 'fill-hover', min: AA_TEXT },
  { key: 'filled_button_visible', ink: 'fill', surface: 'ground-0', min: AA_NON_TEXT },
  { key: 'panel_text', ink: 700, surface: 50, min: AA_TEXT },
  { key: 'link_on_card', ink: 600, surface: 'ground-0', min: AA_TEXT },
  { key: 'link_on_page', ink: 600, surface: 'ground-50', min: AA_TEXT },
  // ⚠ A ROLE since F7b, and gated in both modes now. It measured `brand-500` — the identity stop,
  // which cannot move between modes — so a dark tenant colour drew an invisible dot on a dark card.
  { key: 'ui_shape', ink: 'shape', surface: 'ground-0', min: AA_NON_TEXT },
]

export interface Check {
  key: string
  /** Which mode this row was measured in. The server sends it too, on every row. */
  mode: ThemeMode
  ratio: number
  min: number
  passes: boolean
}

function channel(value: number): number {
  const s = value / 255
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
}

export function relativeLuminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

/** WCAG contrast between two colours. Symmetric — the order never matters. */
export function contrastRatio(a: Rgb, b: Rgb): number {
  const la = relativeLuminance(a)
  const lb = relativeLuminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

function tripletToRgb(triplet: string): Rgb | null {
  const parts = triplet.trim().split(/\s+/)
  if (parts.length !== 3) return null
  const nums = parts.map((p) => Number(p))
  if (nums.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return null
  return nums as Rgb
}

function resolve(
  ref: number | string, ramp: Record<number, string>, mode: ThemeMode,
): Rgb | null {
  // A ROLE name lands on a different step per mode — see BRAND_ROLE.
  if (typeof ref === 'string' && ref.startsWith('fill')) {
    ref = BRAND_ROLE[mode][(ref.slice(5) || 'fill') as 'fill' | 'hover' | 'ink']
  } else if (ref === 'shape') {
    ref = BRAND_ROLE[mode].shape
  }
  if (typeof ref === 'string') return SURFACES[mode][ref] ?? null
  return tripletToRgb(ramp[ref] ?? '')
}

/** Every pair, measured for one brand colour in ONE mode. */
export function checkColour(hex: string, mode: ThemeMode = 'light'): Check[] {
  const ramp = brandRamp(hex, mode)
  const out: Check[] = []
  for (const pair of PAIRS) {
    const ink = resolve(pair.ink, ramp, mode)
    const surface = resolve(pair.surface, ramp, mode)
    if (!ink || !surface) continue
    const ratio = contrastRatio(ink, surface)
    out.push({
      key: pair.key, mode, ratio: Math.round(ratio * 100) / 100,
      min: pair.min, passes: ratio >= pair.min,
    })
  }
  return out
}

/** ⚠ WHAT THE PICKER SHOULD CALL. A colour is stored once and rendered in BOTH modes, so a screen
 *  reporting only the light numbers tells somebody their colour is fine while the gate that saves
 *  it disagrees. `checkColour(hex)` stays for the single-mode question. */
export function checkColourBothModes(hex: string): Check[] {
  return [...checkColour(hex, 'light'), ...checkColour(hex, 'dark')]
}

export function isReadable(hex: string): boolean {
  return checkColourBothModes(hex).every((c) => c.passes)
}

/** A 6-digit hex, the only shape the server accepts. Anything else is not yet a colour. */
export function isHexColour(value: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(value.trim())
}
