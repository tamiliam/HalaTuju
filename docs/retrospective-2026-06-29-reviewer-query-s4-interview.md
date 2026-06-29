# Retrospective — Reviewer-query automation S4: interview guide + gap-spotter seeding

**Date:** 2026-06-29
**Branch:** `feat/reviewer-query-s4-interview`
**Migration:** none
**Roadmap:** `docs/scholarship/reviewer-query-automation-roadmap.md` (S4)

## What Was Built
The interview (Check 3) layer now targets the sponsor's three "what we need to know" buckets:

- **Gap-spotter seeded with the sponsor framework.** `gap_engine.GAP_PROMPT` was restructured to
  organise its questions around the sponsor's three buckets — **academic_resilience /
  financial_need / pathway_confidence** — with the canonical probes named (favourite-vs-hardest
  subject, help-seeking/tuition, full-household affordability, part-time work, first-choice-vs-offer,
  reporting obstacles), and told to target whichever buckets the record leaves UNanswered. Each gap
  now also returns a `bucket` (validated in `_normalise_gaps`; schema updated). The model still
  obeys the existing rails (≤3, don't re-ask answered, supportive framing, today's date, JSON only).
- **Interviewer-guide reference card** in the cockpit interview section — a collapsible checklist of
  the three buckets + their key questions (i18n en/ms/ta), the human counterpart to the AI gaps.
  Display-only; findings are still captured in the existing `InterviewSession`.

## Scope corrections (made by reading the existing code)
- **The high-utility reviewer probe (carried over from S2) was already implemented** —
  `anomaly_engine._detect_utility_high_vs_income` flags it and it flows into the gap-spotter via
  `_flags_summary`. No new work needed; the seeded prompt now turns such flags into bucket-2 probes.
- **The heavyweight "structured guide with new captured fields" was deliberately NOT built.** The
  gap-spotter already drives the reviewer's questions and `InterviewSession` already captures
  findings/rubric/note, so new structured-capture columns would duplicate that. The static guide
  card + the bucket-targeted gaps deliver the intent (the sponsor's questions get asked + answered)
  without a speculative schema/UI build. If the owner later wants per-bucket structured capture,
  that's a clean follow-up.

## What Went Well
- The two existing seams (the gap-spotter prompt + the anomaly→flags→prompt path) meant S4 was a
  prompt restructure + a display card — high leverage, low risk, fully mockable in tests.
- Adding `bucket` was additive: existing gap tests pass (gaps default to `other`), the FE ignores
  the new field unless it wants to group by it.

## What Went Wrong
- Nothing notable. The main judgement was scope (not building duplicate capture machinery), made by
  reading what `InterviewSession` + the gap-spotter already do.

## Numbers
- Tests: backend 1742 pytest (+2 gap-bucket tests), frontend 387 jest. i18n parity 2978×3 (+14). No migration.
- Files touched: ~7.

## Next
S5 (final) — restructure the draft + Pro-refine sponsor-profile prompts to organise their output
around the same three buckets, folding in the bucket-tagged interview answers — so the profile a
sponsor reads "checks the boxes".
