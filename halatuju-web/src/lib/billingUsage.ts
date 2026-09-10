/**
 * Billing & usage v1 (Sprint 13a) — pure presentation helpers for /admin/billing.
 *
 * Node-testable, no React, no i18n objects: label KEYS only (the page resolves them via
 * t()). Units and token counts ONLY — there are NO prices anywhere in v1.
 */
import type {
  AiJobRow, BillingModelRow, BillingOrgBlock, BillingServiceRow,
} from '@/lib/admin-api'

// The metered services, in the order the breakdown table renders them. Each maps to an
// i18n label key admin.billing.service.<service>. (SMS verification is NOT metered — it is
// rendered as a greyed "paused" row, see PAUSED_SERVICES; document storage is a live
// snapshot on the block, not a usage row.)
export const SERVICE_ORDER: string[] = ['gemini', 'vision_ocr', 'openai', 'email', 'whatsapp']

// Rendered greyed/"paused" — phone-verify (Twilio Verify) is paused, so it never meters, but
// the row is shown so the reader knows it exists and costs nothing right now.
export const PAUSED_SERVICES: string[] = ['sms_verify']

// Free, non-metered services listed in the footnote (label keys). Cloudflare Turnstile
// (contact-form verification).
//
// ⚠ **Google Workspace was removed on 2026-09-11 and must not come back.** It was listed here
// as free, and it is not: the owner's August invoice charges MYR 18.90 for it, and it now has
// its own `PlatformCost` source and its own line in the cost section below. A paid subscription
// named in a "these cost nothing" footnote is not a cosmetic error — it is the page telling the
// only person who reads it that a recurring bill does not exist.
export const FREE_SERVICE_KEYS: string[] = ['turnstile']

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

// ── Which AI version did the work, and which is each job set to (2026-09-11) ───────────────

/** Models a service ran, busiest first, then by name so the order never wobbles between loads.
 *  Returns a new array; never mutates the input. An empty list means the service HAS no model
 *  (email, WhatsApp, Cloud Vision OCR) — the caller renders nothing, never "unknown". */
export function orderedModels(row: BillingServiceRow): BillingModelRow[] {
  const rows = row?.models ? [...row.models] : []
  return rows.sort((a, b) => (b.events - a.events) || a.model.localeCompare(b.model))
}

/** Group the AI jobs by the model they are SET TO, busiest group first.
 *
 * ⚠ THIS IS THE SHAPE AN UPGRADE IS PLANNED IN. Reading nineteen rows one at a time answers
 * "what does this job use"; the question actually being asked is the other way round — "if
 * gemini-2.5-flash is replaced, what do I have to touch?" — and that is one group.
 */
export function jobsByModel(jobs: AiJobRow[]): Array<{ model: string; jobs: AiJobRow[] }> {
  const groups = new Map<string, AiJobRow[]>()
  for (const j of jobs || []) {
    const list = groups.get(j.model)
    if (list) list.push(j)
    else groups.set(j.model, [j])
  }
  // `Array.from`, not a spread: this project's tsc target refuses to iterate a Map directly
  // (TS2802), and the repo has 24 of those errors already without adding a 25th.
  return Array.from(groups.entries())
    .map(([model, list]) => ({ model, jobs: list }))
    .sort((a, b) => (b.jobs.length - a.jobs.length) || a.model.localeCompare(b.model))
}

/** The jobs whose model is written into the source, so changing it needs a deploy rather than a
 *  setting. ⚠ Surfaced, not hidden: on an upgrade these are the ones that do NOT move by
 *  themselves, which is the single most useful thing this list can tell its reader. */
export function fixedJobs(jobs: AiJobRow[]): AiJobRow[] {
  return (jobs || []).filter((j) => j.fixed)
}

/** Jobs that fall through to a DIFFERENT PROVIDER when their own runs out of options — a second
 *  key and a second bill. Exactly one today, and it has never fired, which is why an upgrade pass
 *  would otherwise walk straight past it. */
export function secondProviderJobs(jobs: AiJobRow[]): AiJobRow[] {
  return (jobs || []).filter((j) => !!j.fallback_provider)
}
