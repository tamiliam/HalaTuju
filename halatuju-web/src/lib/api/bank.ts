/**
 * Post-award, before any money moves: the payout account, the comprehension quiz that proves
 * the student read the agreement, and the guarantor's one-time phone PIN.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'

// ── Post-award: bank-details capture (payout account) ────────────────────
// An awarded/active student uploads a bank statement (field-extracted), then
// confirms the three fields. The holder MUST be the student (server hard-gate;
// a mismatch throws err.code='bank_holder_mismatch'). Stored only — not displayed.

export interface BankAccount {
  bank_name: string
  account_number: string
  account_holder: string
  holder_verdict: string
  confirmed_at: string | null
  updated_at: string
}

export async function getBankAccount(
  options?: ApiOptions
): Promise<{ bank_account: BankAccount | null }> {
  return apiRequest('/api/v1/scholarship/bank-account/', options)
}

export async function confirmBankAccount(
  body: { bank_name: string; account_number: string; account_holder: string },
  options?: ApiOptions,
): Promise<BankAccount> {
  return apiRequest('/api/v1/scholarship/bank-account/', {
    method: 'POST',
    body: JSON.stringify(body),
    ...options,
  })
}

/** One comprehension checkpoint as served by the API (matches the ContractClause quiz
 *  shape: options is a 3-string array, `correct` is the 0-based index). */
export interface ComprehensionCheckpoint {
  tag: string
  plain: string
  question: string
  options: string[]
  correct: number
  why: string
}
export interface ComprehensionQuizData {
  template_version: string
  locale_used: string
  checkpoints: ComprehensionCheckpoint[]
}

/** GET the comprehension checkpoints for the caller's awarded application, served from
 *  the governing contract template (en fallback when the locale isn't translated). */
export async function getComprehensionQuiz(locale: string, options?: ApiOptions): Promise<ComprehensionQuizData> {
  return apiRequest(`/api/v1/scholarship/award/comprehension-quiz/?locale=${encodeURIComponent(locale)}`, options)
}

/** Record that the student passed the comprehension quiz — pins `comprehension_template`
 *  to the version they were quizzed on. A stale `template_version` (a redeploy mid-quiz)
 *  → 409 `version_changed`, surfaced as `err.code` so the caller can re-take. */
export async function recordComprehensionPass(
  templateVersion: string, options?: ApiOptions): Promise<{ ok: boolean; template_version: string }> {
  return apiRequest('/api/v1/scholarship/award/comprehension/', {
    method: 'POST',
    body: JSON.stringify({ template_version: templateVersion }),
    ...options,
  })
}

/** Send a one-time PIN to the parent/guardian SURETY's pre-declared, LOCKED phone
 *  (read server-side from the student's guardians list) — the same-session parent gate
 *  before the bursary signature. Returns a masked hint ("•••• 2222") only; never the
 *  full number. The student cannot supply or edit the number. */
export async function sendGuarantorPin(
  options?: ApiOptions,
): Promise<{ status: string; phone_hint: string }> {
  return apiRequest('/api/v1/scholarship/award/guarantor/verify-phone/send/', {
    method: 'POST',
    body: JSON.stringify({}),
    ...options,
  })
}

/** Confirm the parent PIN. On success the server stamps the application so the
 *  guarantor signature is unlocked; a wrong/expired code → a 400 (thrown). */
export async function checkGuarantorPin(
  code: string,
  options?: ApiOptions,
): Promise<{ verified: boolean }> {
  return apiRequest('/api/v1/scholarship/award/guarantor/verify-phone/check/', {
    method: 'POST',
    body: JSON.stringify({ code }),
    ...options,
  })
}

