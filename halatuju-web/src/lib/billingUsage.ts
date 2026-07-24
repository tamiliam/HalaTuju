/**
 * Billing & usage v1 (Sprint 13a) — pure presentation helpers for /admin/billing.
 *
 * Node-testable, no React, no i18n objects: label KEYS only (the page resolves them via
 * t()). Units and token counts ONLY — there are NO prices anywhere in v1.
 */
import type { BillingOrgBlock, BillingServiceRow } from '@/lib/admin-api'

// The metered services, in the order the breakdown table renders them. Each maps to an
// i18n label key admin.billing.service.<service>. (SMS verification is NOT metered — it is
// rendered as a greyed "paused" row, see PAUSED_SERVICES; document storage is a live
// snapshot on the block, not a usage row.)
export const SERVICE_ORDER: string[] = ['gemini', 'vision_ocr', 'openai', 'email', 'whatsapp']

// Rendered greyed/"paused" — phone-verify (Twilio Verify) is paused, so it never meters, but
// the row is shown so the reader knows it exists and costs nothing right now.
export const PAUSED_SERVICES: string[] = ['sms_verify']

// Free, non-metered services listed in the footnote (label keys). Google Workspace
// (Meet/Calendar/Drive/Sheets) + Cloudflare Turnstile (contact-form verification).
export const FREE_SERVICE_KEYS: string[] = ['workspace', 'turnstile']

/** Order a block's service rows by SERVICE_ORDER (known first in that order, any unknown
 * service appended alphabetically). Returns a new array; never mutates the input. */
export function orderedServices(block: BillingOrgBlock): BillingServiceRow[] {
  const rows = block?.services ? [...block.services] : []
  const rank = (s: string) => {
    const i = SERVICE_ORDER.indexOf(s)
    return i === -1 ? SERVICE_ORDER.length : i
  }
  return rows.sort((a, b) => {
    const ra = rank(a.service)
    const rb = rank(b.service)
    return ra !== rb ? ra - rb : a.service.localeCompare(b.service)
  })
}

/** Human-readable byte size (binary units): 0 → "0 B", 1024 → "1 KB", up to TB. Deterministic,
 * locale-agnostic, one decimal from MB up. */
export function formatBytes(bytes: number): string {
  const n = Number(bytes) || 0
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let val = n / 1024
  let u = 0
  while (val >= 1024 && u < units.length - 1) {
    val /= 1024
    u += 1
  }
  const rounded = u === 0 ? Math.round(val) : Math.round(val * 10) / 10
  return `${rounded} ${units[u]}`
}

/** Compact integer for a tile (thousands grouping). */
export function formatCount(n: number): string {
  return (Number(n) || 0).toLocaleString('en-GB')
}

/** 'YYYY-MM' → e.g. 'July 2026' (English month names — the picker still shows the code). A
 * malformed value is returned unchanged. */
export function formatMonth(month: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(month || '')
  if (!m) return month || ''
  const names = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December']
  const idx = parseInt(m[2], 10) - 1
  if (idx < 0 || idx > 11) return month
  return `${names[idx]} ${m[1]}`
}
