/**
 * Resolution tickets — the Student Action Centre: what we have asked the student for, and
 * what they send back.
 *
 * ⚠ `ResolutionItem` is one half of a keep-in-sync pair with `AdminResolutionItem` in
 * `admin-api/resolution.ts`, and the two have fallen out of step (TD-266).
 * drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'

// ── Resolution tickets — the Student Action Centre (Sprint 4) ────────────
// A self-service "things to finish" queue. The backend raises a ticket for each
// verification gap (a missing/unreadable document, a mismatch the student must
// explain, or a fact to re-check). Officers can also raise free-text tickets.
// Each ticket carries a `kind` that decides how the student resolves it:
//   doc         → upload the named `doc_type`
//   explanation → type a short reply (POST /resolve/ with { text })
//   confirm     → review/fix the relevant section; the ticket auto-clears
//                 server-side once the underlying gap closes.
export interface ResolutionItem {
  id: number
  fact: string
  code: string
  // string[] supports the income reason codes' `members` list (e.g. ['father','brother']);
  // boolean supports flags like `needs_officer_eye` (the circuit-breaker escalation).
  params: Record<string, string | number | boolean | string[]>
  prompt: string
  // 'clarify'/'human' added by Check 2 STEP 2 (an AI student query / a reviewer-only item).
  kind: 'doc' | 'confirm' | 'explanation' | 'clarify' | 'human'
  doc_type: string
  status: string
  source: 'system' | 'officer' | 'check2'
  resolution_text: string
  created_at: string
  resolved_at: string | null
  // Vircle setup task only: the account type Vircle's birth-year rule expects the student to
  // have registered ('principal' born ≤2008, 'child' after). null on every other item; a
  // payload predating the field degrades to 'principal' in the card (lib/vircleAccount.ts).
  vircle_expected?: 'principal' | 'child' | null
}

export async function getResolutionItems(
  options?: ApiOptions
): Promise<{ open: ResolutionItem[]; resolved: ResolutionItem[]; set_aside?: ResolutionItem[] }> {
  return apiRequest('/api/v1/scholarship/resolution-items/', options)   // trailing slash: no 301 on the hottest post-submit fetch
}

export async function resolveResolutionItem(
  id: number,
  text: string,
  options?: ApiOptions,
  // The displayed question — sent so the backend can judge a typed answer's relevance
  // (Phase 2). Off-topic → response is `{ resolved: false, nudge }` (task stays open).
  question?: string,
  // V2a (2026-09-09): the eWallet ID now arrives via Vircle's Airtable callback, so the
  // Action Centre no longer sends this. Kept because the server still accepts (and
  // validates) a supplied value — an old cached bundle may send one.
  vircleId?: string,
  // Vircle setup only: the student's own claim of which account type they registered
  // ('principal'/'child') — stored on the item for the human reconciling a callback
  // `no_match`; the coaching happens in the card before this is sent.
  accountType?: string,
  // Vircle setup only (owner, 2026-09-10, off a real "confirmed but never registered" case):
  // the student's explicit tick that they installed AND registered before confirming. The
  // card refuses to send without it; the server stores the claim but does not require it,
  // so an old cached bundle keeps working.
  installedConfirmed?: boolean,
): Promise<ResolutionItem & { resolved?: boolean; nudge?: string }> {
  return apiRequest(`/api/v1/scholarship/resolution-items/${id}/resolve/`, {
    method: 'POST',
    body: JSON.stringify({
      text, question, vircle_id: vircleId, account_type: accountType,
      installed_confirmed: installedConfirmed,
    }),
    ...options,
  })
}

