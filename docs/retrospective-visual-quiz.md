# Retrospective — Visual Quiz Redesign (v1.27.0)

**Date:** 10 March 2026
**Sprint:** Visual Quiz Redesign (post-Sprint 20)

## What Was Built

Complete quiz redesign from 6 radio-button questions to 8+1 visual card questions with:
- 2×2 icon card grids with emoji icons
- Multi-select (pick up to 2) on Q1 and Q2 with weight splitting
- Conditional Q2.5 branching for heavy industry sub-fields
- "Not Sure Yet" option on Q1, Q2, Q4
- New `field_interest` signal category (11 signals, ±8 cap)
- Field interest matching against course `frontend_label`
- New signal wiring: `rote_tolerant`, `high_stamina`, `quality_priority`
- Dead signal cleanup
- Full i18n (EN/BM/TA) with interpolation support

## What Went Well

1. **Subagent-driven development** worked smoothly — 10 tasks executed sequentially with fresh context per task
2. **Stitch mockups first** — designing all 10 screens before coding prevented rework
3. **Comprehensive test coverage** — 24 quiz + 16 ranking tests caught edge cases early
4. **Design doc quality** — the two-advisor review process produced a thorough, defensible design

## What Went Wrong

1. **GCP config drift** — after the first deploy, GCP config silently reverted to `admin@tamilfoundation.org` / `sjktconnect`. The second frontend deploy went to the wrong project, creating a new service. User saw no change. **Fix**: Always verify `gcloud config get account && gcloud config get project` immediately before every deploy, even if set earlier in the session.
2. **Stitch designs initially ignored** — first implementation used a generic card design instead of matching the Stitch mockups. User had to explicitly ask "Why create the designs, only to be discarded?" **Lesson**: When Stitch mockups exist, they ARE the spec — code to match them exactly.
3. **Redundant Next button** — initial implementation had both auto-advance and a Next button. User correctly identified this as confusing. **Lesson**: Think through UX interactions before adding navigation controls.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Auto-advance, no Next button | Tapping a card IS the navigation. Next button creates confusion about whether tap or button advances. |
| Weight splitting (3→2) | Prevents multi-select from doubling signal strength. 2 picks = broader interest, not stronger. |
| "Not Sure Yet" = exclusive | Mixing "Not Sure" with specific picks is contradictory. |
| Q2.5 conditional only | 88 heavy industry courses need sub-differentiation; other categories don't. |
| Field interest cap ±8, work preference ±4 | Field is primary differentiator (higher cap), work preference is secondary (lower cap). |
| Dead signal removal | `organising`, `meaning_priority` etc. had no matching rules — just noise. |

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Quiz questions | 6 | 8+1 (conditional) |
| Signal categories | 5 | 6 (added field_interest) |
| Total signals | ~15 | 22 |
| Quiz tests | 14 | 24 |
| Ranking tests | 34 | 50 |
| Total tests | 188 | 212 (203 pass) |
| Golden master | 8280 | 8245 |
| Backend commits | — | 5 |
| Frontend commits | — | 3 |
