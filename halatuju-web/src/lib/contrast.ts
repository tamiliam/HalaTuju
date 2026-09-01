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
import { brandRamp } from '@/lib/branding'

export type Rgb = [number, number, number]

/** WCAG AA for normal-size text. Every pair below carries words except `ui_shape`. */
export const AA_TEXT = 4.5

/** WCAG AA for non-text: a shape whose boundary must be discernible, not read. */
export const AA_NON_TEXT = 3.0

/** The light-mode platform surfaces. `white` and `ground-0` are separate on purpose — `text-white`
 *  is a literal in this codebase and deliberately never became `text-ground-0`. */
const GROUND_0: Rgb = [255, 255, 255]
const GROUND_50: Rgb = [249, 250, 251]
const WHITE: Rgb = [255, 255, 255]

export interface Pair {
  /** The server's key for this pair. Do not rename one side only. */
  key: string
  /** Which ramp step the INK comes from, or 'white' for the literal. */
  ink: number | 'white'
  /** Which ramp step the SURFACE comes from, or a platform ground. */
  surface: number | 'ground-0' | 'ground-50'
  min: number
}

/**
 * The pairs the product renders, counted in `src/**` rather than imagined.
 *
 * `ui_shape` carries a different bar because `bg-primary-500` no longer carries text: A2 moved 52
 * filled controls off it onto `-600`, leaving dots, progress bars, toggles and aria-hidden icon
 * circles. Holding a shape to the text bar is what made the gate refuse the platform's own colour.
 */
export const PAIRS: Pair[] = [
  { key: 'filled_button', ink: 'white', surface: 600, min: AA_TEXT },
  { key: 'filled_button_dark', ink: 'white', surface: 700, min: AA_TEXT },
  { key: 'panel_text', ink: 700, surface: 50, min: AA_TEXT },
  { key: 'link_on_card', ink: 600, surface: 'ground-0', min: AA_TEXT },
  { key: 'link_on_page', ink: 600, surface: 'ground-50', min: AA_TEXT },
  { key: 'ui_shape', ink: 'white', surface: 500, min: AA_NON_TEXT },
]

export interface Check {
  key: string
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

function resolve(ref: Pair['ink'] | Pair['surface'], ramp: Record<number, string>): Rgb | null {
  if (ref === 'white') return WHITE
  if (ref === 'ground-0') return GROUND_0
  if (ref === 'ground-50') return GROUND_50
  return tripletToRgb(ramp[ref as number] ?? '')
}

/** Every pair, measured for one brand colour in LIGHT mode — the only mode gated today. */
export function checkColour(hex: string): Check[] {
  const ramp = brandRamp(hex, 'light')
  const out: Check[] = []
  for (const pair of PAIRS) {
    const ink = resolve(pair.ink, ramp)
    const surface = resolve(pair.surface, ramp)
    if (!ink || !surface) continue
    const ratio = contrastRatio(ink, surface)
    out.push({ key: pair.key, ratio: Math.round(ratio * 100) / 100, min: pair.min, passes: ratio >= pair.min })
  }
  return out
}

export function isReadable(hex: string): boolean {
  return checkColour(hex).every((c) => c.passes)
}

/** A 6-digit hex, the only shape the server accepts. Anything else is not yet a colour. */
export function isHexColour(value: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(value.trim())
}
