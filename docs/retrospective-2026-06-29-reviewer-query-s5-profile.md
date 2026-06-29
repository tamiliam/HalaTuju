# Retrospective — Reviewer-query automation S5: final-profile prompt restructure

**Date:** 2026-06-29
**Branch:** `feat/reviewer-query-s5-profile`
**Migration:** none
**Roadmap:** `docs/scholarship/reviewer-query-automation-roadmap.md` (S5 — the final sprint)

## What Was Built
The profile a sponsor reads is now organised around the sponsor's three "need to know" areas —
**Financial need / Academic commitment & resilience / Pathway & enrolment confidence** — the same
buckets `gap_engine` tags interview gaps with (S4). This is the payoff sprint: S1–S4 captured the
raw material (full-household income, stale-doc/sibling clarifies, reporting date, bucket-tagged
interview gaps); S5 makes the final document actually answer the sponsor's questions.

- **Shared `_COVERAGE` instruction** (`profile_engine.py`) injected into BOTH prompts (draft
  `PROFILE_PROMPT` + Pro-refine `REFINE_PROMPT`): the profile must answer all three areas, woven
  into the prose. It is a COVERAGE instruction, not a layout one — the warm-narrative rules hold
  (still **no headings, no lists**, ~three short paragraphs, he/she, ethnicity-safe, income honesty).
- **`_STYLE` re-ordered** so the three paragraphs map onto the three areas (family situation & why
  the assistance is needed → academic standing & the resilience behind it → the pathway ahead, the
  confirmed place, reporting date, and readiness to take it up).
- **Interview findings grouped by bucket** in `_render_interview`: each finding is filed under its
  gap's `bucket` (financial → academic → pathway → other), so the refine can weave each into the
  matching part of the narrative. A refine rule names the grouping explicitly.
- The new household-income clarify answers (S1–S3) already flow into both prompts via `_render_qa` —
  no extra plumbing needed; the coverage block tells the model to land them in Financial need.
- **`PROMPT_VERSION` bumped `2026-06-18.1` → `2026-06-29.1`** (lessons.md / the #18 trap) so existing
  drafts are detectable as stale by VERSION and the `backfill-assigned-profiles` cron can refresh them.

## Scope corrections (made by reading the existing code)
- **No new structured fields, no migration, no FE, no i18n.** The buckets already exist on the gaps
  (S4); the Q&A already feeds the prompt; the profile is rendered as plain markdown the FE already
  shows. S5 is purely the two Gemini prompts + the findings-grouping helper.
- Kept the change a COVERAGE instruction rather than mandating headed sections — the owner's settled
  decision is ONE warm PII-redacted narrative (decisions.md, 2026-06-15); headed buckets would have
  broken that. The three areas are guaranteed by instruction, not by layout.

## What Went Well
- The S4 `bucket` field was the seam: grouping findings by it was a small, additive helper change,
  and existing refine tests (gaps with no bucket → "Other") keep passing unchanged.
- Fully mockable — `_call_gemini_text` is patched in every test; zero billable calls in CI.

## What Went Wrong
- Nothing notable. The one judgement was coverage-vs-layout (above), resolved against the
  settled single-narrative decision rather than guessing.

## Design Decisions
- **Sponsor framework as a COVERAGE instruction, not headed sections** — see decisions.md
  (2026-06-29). Preserves the single warm narrative while guaranteeing the three areas are answered.

## Numbers
- Tests: backend **1748 scholarship pytest** (+6: 1 draft-coverage, 1 refine-coverage, 1 bucket-
  grouping, and the existing suite). No migration. Frontend/i18n untouched (0 web files).
- Files touched: ~5 (profile_engine.py, 2 test files, roadmap, retro + decisions/changelog).

## Next
**The reviewer-query automation roadmap is COMPLETE (S1–S5, all dark/post-shortlist).** Optional
follow-up: a billable `backfill-assigned-profiles` cron run to regenerate existing drafts onto
`2026-06-29.1` (owner's call — new generations after deploy already use the new prompt). Per-bucket
structured interview-capture fields remain a deferred clean follow-up (S4 note).
