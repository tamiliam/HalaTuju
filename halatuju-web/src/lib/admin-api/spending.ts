/**
 * Sponsor spending S4: the officer's screen — by merchant, by student, and the category a
 * transaction is filed under.
 */
import { API_BASE, adminFetch, giftQuery } from './client'
import type { ApiOptions } from './client'

// ── Sponsor spending S4 — the officer's screen ───────────────────────
//
// ⚠ Money arrives as a STRING and stays one. It is summed, compared against a released total
// and shown to a person; a float would round it. Format at the edge, never parse to Number
// and back.
//
// ⚠ `last_seen` is a DATE with no time, and cannot be otherwise: the hour is discarded at
// import so that nothing downstream can ever show what time a student ate.
export interface SpendingMerchantRow {
  merchant: string
  category: string
  /** Which rung decided it: '' | 'duitnow' | 'rule' | 'inferred' | 'ai' | 'owner'. */
  decided_by: string
  visits: number
  total: string
  last_seen: string | null
  /** Payments the RM20 per-row ceiling kept out of `food` at a food-pattern shop. */
  held_back: number
  /** When the stored verdict was REACHED — not when a student last shopped here (`last_seen`).
   *  `null` for a shop with no stored verdict at all. Added S7 when the separate
   *  "what the model decided recently" list was deleted: it held exactly one fact this row did
   *  not, so the fact became a column on the row you can actually correct. */
  decided_at: string | null
}

export interface SpendingStudentRow {
  application_id: number
  name: string
  /** Things the student BOUGHT — rows in the Vircle export. ⚠ Was `payments`, which beside
   *  `paid` and `balance` read as the number of disbursements (owner, 2026-09-12). */
  transactions: number
  spent: string
  unplaced: string
  /** Released to this student to date — the same source the sponsor card uses. */
  paid: string
  /** `paid` minus `spent`. ⚠ CAN BE NEGATIVE and is deliberately not floored: the wallet is
   *  the student's own and a parent may top it up. The sponsor card floors its version; an
   *  officer gets the real figure, because they are the one who should ask about it. */
  balance: string
}

export interface SpendingOverview {
  totals: {
    spent: string
    placed: string
    unplaced: string
    placed_pct: number
    merchants_to_check: number
  }
  merchants: SpendingMerchantRow[]
  students: SpendingStudentRow[]
  wallet_gaps: {
    /** Students a COMPLETED run paid on or before `data_to`, for whom we hold no spending
     *  at all. ⚠ Replaced `students_without_wallet` on 2026-09-12: that list named funded
     *  students with no wallet id **whom nobody had paid**, which blocks nothing and which
     *  the Payments screen already refuses to pay. This is the question a person asks. */
    unseen_students: {
      application_id: number; name: string
      /** Released to them, and what we can see of their spending — zero for every row on
       *  today's rule, and computed rather than assumed so it stays true if that changes. */
      paid: string; spent: string
    }[]
    shared_wallets: Record<string, number[]>
    /** The newest transaction date we hold, or null before the first import. */
    data_to: string | null
  }
  /** The ten codes, served BY THE SERVER from the model choices so the dropdown cannot drift
   *  away from what the database will accept. Never hard-code this list here. */
  categories: { code: string; label: string }[]
}

export async function getSpendingOverview(programme?: string, options?: ApiOptions) {
  return adminFetch<SpendingOverview>(
    `/api/v1/admin/scholarship/spending/${giftQuery(programme)}`, options)
}

/** Correct one shop's category. The verdict outranks every rung of the sorter, for ever. */
export async function setSpendingCategory(
  merchant: string, category: string, programme: string | undefined, options?: ApiOptions,
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(
    `${API_BASE}/api/v1/admin/scholarship/spending/category/${giftQuery(programme)}`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ merchant, category }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.code || body.error || `Admin API error: ${res.status}`)
  }
  return res.json() as Promise<{
    merchant: string; category: string; decided_by: string; rows_changed: number
  }>
}
