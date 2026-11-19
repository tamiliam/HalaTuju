/**
 * Made-up "AI prediction" payloads for the section and landing tests (LL1). Nobody real is in here:
 * the reviewers are invented names, and every figure is invented to be easy to find on the screen.
 */
import type { PredictionCounts, QcCheckedCounts, ReviewerRow, VerdictMetrics } from '@/lib/admin-api'

/** LL2b: one block of "checked by the QC" counts. */
export const qcChecked = (over: Partial<QcCheckedCounts> = {}): QcCheckedCounts => ({
  in_doubt: 0, checked: 0, not_checked: 0, agreed: 0, disagreed: 0, ai_green_checked: 0,
  ai_wrong_checked: 0, ai_right_reviewer_wrong_checked: 0, few: false, few_ai_green: false, ...over,
})

export const counts = (over: Partial<PredictionCounts> = {}): PredictionCounts => ({
  green: 100, green_failed: 10, green_agreed: 90, green_agree_rate: 0.9, green_fail_rate: 0.1,
  unsure: 40, unsure_passed: 30, unsure_pass_rate: 0.75,
  few_green: false, few_unsure: false, few: false, ...over,
})

export const reviewer = (over: Partial<ReviewerRow> = {}): ReviewerRow => ({
  ...counts(), id: 7, name: 'Test Reviewer One', label_key: null, applications: 12, ...over,
})

export const metrics = (over: Partial<VerdictMetrics> = {}): VerdictMetrics => ({
  applications: 50, fact_decisions: 200, overrides: 20, override_rate: 0.1, per_fact: {},
  overall: counts(),
  fact_counts: {
    identity: counts({ green: 50, green_agreed: 49, green_agree_rate: 0.98 }),
    academic: counts({ green: 30, green_agreed: 27, green_agree_rate: 0.9 }),
    pathway: counts({ green: 10, green_agreed: 6, green_agree_rate: 0.6 }),
    income: counts({ green: 10, green_agreed: 8, green_agree_rate: 0.8 }),
  },
  by_version: {
    'v5.1': counts({ green: 60, green_agreed: 57, green_agree_rate: 0.95 }),
    '': counts({ green: 40, green_agreed: 33, green_agree_rate: 0.825 }),
  },
  by_month: {
    '2026-08': counts({ green: 20, green_agreed: 17, green_agree_rate: 0.85 }),
    '2026-09': counts({ green: 3, green_agreed: 3, green_agree_rate: 1, few_green: true }),
    '2026-10': counts({ green: 40, green_agreed: 38, green_agree_rate: 0.95 }),
  },
  doubt_codes: [
    { fact: 'income', code: 'income_unclear', passed: 18, failed: 2, total: 20, fail_rate: 0.1, pass_rate: 0.9, few: false },
    { fact: 'academic', code: 'grade_blurred', passed: 3, failed: 1, total: 4, fail_rate: 0.25, pass_rate: 0.75, few: true },
  ],
  qc_agreement: {
    accept: 17, reopen: 2, reject: 1, total: 20, accept_rate: 0.85, few: false,
    by_month: {},
  },
  ...over,
})

/** The same payload as a lead is served it: with the reviewer table. */
export const leadMetrics = (): VerdictMetrics => metrics({
  by_reviewer: [
    reviewer(),
    reviewer({ id: null, name: 'x', label_key: 'unmatched_reviewer', applications: 3 }),
    reviewer({ id: null, name: 'y', label_key: 'unnamed_reviewer', applications: 2 }),
  ],
})
