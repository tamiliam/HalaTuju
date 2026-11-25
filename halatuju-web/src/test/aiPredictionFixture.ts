/**
 * Made-up "AI prediction" payloads (F4 shape) for the section and landing tests. Nobody real is in
 * here: the reviewers are invented names, and every figure is invented to be easy to find on screen.
 */
import type { FactScore, PredictionCounts, ReviewerRow, ScoreBlock, VerdictMetrics } from '@/lib/admin-api'

export const block = (over: Partial<ScoreBlock> = {}): ScoreBlock => ({
  facts: 100, points: 150, best: 200, lost: -30, score_pct: 75,
  right_sure: 60, right_leaning: 20, unsure: 10, wrong_leaning: 6, wrong_sure: 4, ...over,
})

export const factScore = (over: Partial<FactScore> = {}): FactScore => ({
  ...block(), top_reasons: [], ...over,
})

export const counts = (over: Partial<PredictionCounts> = {}): PredictionCounts => ({
  green: 100, green_failed: 10, green_agreed: 90, green_agree_rate: 0.9, green_fail_rate: 0.1,
  unsure: 40, unsure_passed: 30, unsure_pass_rate: 0.75,
  few_green: false, few_unsure: false, few: false, ...over,
})

export const reviewer = (over: Partial<ReviewerRow> = {}): ReviewerRow => ({
  ...counts(), id: 7, name: 'Test Reviewer One', label_key: null, applications: 12,
  qc_accepted: 9, qc_sent_back: 2, ...over,
})

/** The payload an organisation admin is served: score only, no `by_reviewer` / `ai_team`. */
export const metrics = (over: Partial<VerdictMetrics> = {}): VerdictMetrics => ({
  applications: 187,
  score: {
    ...block({ facts: 775, points: 736, best: 1550, lost: -390, score_pct: 47 }),
    not_scored: 0,
    most_lost: { fact: 'pathway', points: -156 },
    by_fact: {
      identity: factScore({ facts: 200, points: 268, best: 400, lost: -52, score_pct: 67,
        right_sure: 150, right_leaning: 20, unsure: 22, wrong_leaning: 4, wrong_sure: 4,
        top_reasons: [{ key: 'fail:documents_differ', points: -30 }, { key: 'fail:not_given', points: -20 }] }),
      academic: factScore({ facts: 200, points: 224, best: 400, lost: -78, score_pct: 56,
        top_reasons: [{ key: 'fail:interview_differs', points: -50 }, { key: 'pass:ruleNotMet', points: -28 }] }),
      pathway: factScore({ facts: 204, points: 108, best: 408, lost: -156, score_pct: 26,
        top_reasons: [{ key: 'pass:unverifiable', points: -100 }] }),
      income: factScore({ facts: 171, points: 136, best: 342, lost: -104, score_pct: 40 }),
    },
  },
  ...over,
})

/** As a lead is served it: with the reviewer table. */
export const leadMetrics = (): VerdictMetrics => metrics({
  by_reviewer: [
    reviewer(),
    reviewer({ id: null, name: 'x', label_key: 'unmatched_reviewer', applications: 3 }),
    reviewer({ id: null, name: 'y', label_key: 'unnamed_reviewer', applications: 2 }),
  ],
})

/** As a super is served it: with the reviewer table and the "For the AI team" part. */
export const superMetrics = (): VerdictMetrics => ({
  ...leadMetrics(),
  ai_team: {
    doubt_codes: [
      { fact: 'income', code: 'income_unclear', passed: 18, failed: 2, total: 20, fail_rate: 0.1, pass_rate: 0.9, few: false },
      { fact: 'academic', code: 'grade_blurred', passed: 3, failed: 1, total: 4, fail_rate: 0.25, pass_rate: 0.75, few: true },
    ],
    by_version: [
      { version: 'v5.1', ...block({ facts: 260, points: 210, best: 520, score_pct: 40 }) },
      { version: '', ...block({ facts: 290, points: -20, best: 580, score_pct: -3 }) },
    ],
  },
})
