// Structural guardrails for the comprehension quiz (code-health S3 #10).
// Content fidelity to bursary.py's AGREEMENT_CLAUSES is a human review duty (the
// clause map is documented at the top of CHECKPOINTS); these tests pin what CAN be
// mechanically pinned: shape, locale parity, and single-correct-answer per question.
import { CHECKPOINTS, CHECKPOINT_COUNT, checkpointsFor, quizUiFor } from '@/lib/awardComprehension'

const LOCALES = ['en', 'ms', 'ta'] as const

describe('award comprehension quiz structure', () => {
  it('has the same checkpoint count in every locale', () => {
    for (const loc of LOCALES) {
      expect(CHECKPOINTS[loc]).toHaveLength(CHECKPOINT_COUNT)
    }
  })

  it('every question has exactly one correct option (of 3), in every locale', () => {
    for (const loc of LOCALES) {
      for (const cp of CHECKPOINTS[loc]) {
        expect(cp.options).toHaveLength(3)
        expect(cp.options.filter((o) => o.correct)).toHaveLength(1)
        expect(cp.tag).toBeTruthy()
        expect(cp.plain).toBeTruthy()
        expect(cp.question).toBeTruthy()
        expect(cp.why).toBeTruthy()
      }
    }
  })

  it('does not reassert the terms the agreement never contained', () => {
    // The 2026-07-03 reconciliation removed: a CGPA figure, a 7-day notice window,
    // and a per-semester upload/suspension duty. None of these exist in
    // AGREEMENT_CLAUSES — if one reappears here, the quiz has drifted from the
    // contract again.
    const en = JSON.stringify(CHECKPOINTS.en)
    expect(en).not.toMatch(/CGPA|3\.0/)
    expect(en).not.toMatch(/7 days|within 7/i)
    expect(en).not.toMatch(/suspended, and continued failure|termination/i)
  })

  it('locale fallback works', () => {
    expect(checkpointsFor('ta')).toBe(CHECKPOINTS.ta)
    expect(checkpointsFor('xx')).toBe(CHECKPOINTS.en)
    expect(quizUiFor('xx').begin).toBeTruthy()
  })
})
