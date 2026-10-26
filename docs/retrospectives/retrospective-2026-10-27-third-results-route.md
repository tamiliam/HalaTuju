# Retrospective — third results route (requests #37, #38, #43), 2026-10-25 → 2026-10-27

Roadmap: `docs/plans/2026-10-25-third-results-route-roadmap.md` (rulings D1–D15 in §7a).
Live: S1 50df8d7f · S2a e4096440 · S2b eddd4ad6 · S3a+S3b 01f8a723 2de36a85 · S4 4bab4086.
Migrations: courses 0084, scholarship 0178 (both applied via MCP before the push). Flag:
THIRD_ROUTE_OPEN=1 on halatuju-api (set before the S2b push).

## What went well
- Every sprint had an adversarial review before push; it found real defects each time (S2a API
  self-escape; S2b sign-in demotion of 55 STPM applicants; S3 post-submit endpoints wiping grades and
  an unclosable ticket; S4 request-keyed promotion and an STPM upload evicting a real SPM slip). None
  reached production.
- Owner-first: before/after lists (S1 ranking, S4 D1 promotion) shown before release.
- Coordinated with the corpus/TD-403 session by message: they pushed first, S3 rebased, version
  numbers agreed (VERDICT_ENGINE_VERSION .2 → .3).

## What to do differently
- The design moved four times mid-sprint (standing link → detection-led notes → read-only type →
  misfile-first). Each change was right, but earlier mock rounds on the hard case (a wrong slip)
  would have saved builder rounds. Mock the failure states, not just the happy path.
- Merges with a parallel session broke three size guards (a 601-line file, a 2-line function
  overrun, the first-load median). Run `test_code_standards` and `bundle-budget` immediately after
  every rebase, before anything else.
- A Cloud Run env change is classified as dangerous by auto mode; ask the owner up front when a
  release needs one.
- Usage limits stopped builders three times; resuming the same agent with SendMessage kept its work.

## Owed
- Code health: cross-app import count rose 52 → 64 from S2a/S2b (exam_questions ↔ scholarship hooks);
  explain or reduce at the next consolidation review (docs/code-health.md).
- Six promoted (D1) rows' sponsor AI profiles still say SPM until a scoped, owner-approved refresh.
- Factory finding: `make_application('profile_complete')` freezes requirements before the D12 mapping;
  tertiary submitted tests must pass an explicit snapshot (candidate debt entry).
- #304 and #337 left for the students to upload their own higher results.
