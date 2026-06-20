// R5 — pure helpers for the Trust & Transparency hub's "sources & uses" bars.
// No React, no DOM — unit-tested in node-env jest (component render is untested).
import type { TrustFigure } from '@/lib/api'

/** Sum a list of {label, amount} figures (amount is a stringified RM value). */
export function figureTotal(figures: TrustFigure[] | null | undefined): number {
  if (!figures) return 0
  return figures.reduce((sum, f) => sum + (Number(f.amount) || 0), 0)
}

/** A figure's share of its total, 0–100, rounded — for the bar width. Guards /0. */
export function figurePercent(amount: string | number, total: number): number {
  const a = Number(amount) || 0
  if (total <= 0) return 0
  const pct = Math.round((a / total) * 100)
  return Math.max(0, Math.min(100, pct))
}

/** Format a stringified RM amount as "RM 12,000". Non-numeric → "RM 0". */
export function formatRM(amount: string | number): string {
  const n = Number(amount) || 0
  return `RM ${Math.round(n).toLocaleString('en-MY')}`
}
