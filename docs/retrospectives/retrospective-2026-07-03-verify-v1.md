# Retrospective — Verification-Model Roadmap Sprint V1 (Slot & Document Integrity)

**Date:** 2026-07-03
**Branch/worktree:** `feat/verify-v1` in `.worktrees/verify-model`
**Roadmap:** `docs/plans/2026-07-03-verification-model-roadmap.md` (V1 of V1–V6)
**Findings source:** `docs/plans/2026-07-03-check-model-audit.md` (#1, #2, F2, F3)
**Migration:** NONE — every choice/schema this touches already existed; changes are Python
constants, extraction schema, verdict logic, i18n, and a serializer field.
**Tests:** 2025 scholarship pytest (+6 net) + 412 jest; tsc clean (17 pre-existing test-file
errors are not ours).

## What Was Built

The audit found two document types that were "boxes that tick themselves" and a systematic
slotting hole. V1 closes all four cited findings without a migration.

- **#1 — `guardianship_letter` wired into the pipeline.** It was a *dead limb*: the Gemini
  schema (`vision._FIELD_SCHEMAS`), the verdict branch (`verdict_engine._verdict_income`),
  the resolution branch (`resolution.doc_match_verdict`), the officer chip
  (`officerCockpit.documentFacts` + serializer `guardianship_check`) and the check
  (`income_engine.student_guardianship_check`) all existed — but the upload never triggered
  its extraction, because it was absent from `views.SUPPORTING_NAME_CHECK_TYPES`. So guardian
  names read blank forever, the relationship could never machine-confirm, and ANY file (even a
  selfie) resolved an officer's guardianship-letter request. Fix: added it to
  `RELATIONSHIP_DOC_TYPES` (⊂ `SUPPORTING_NAME_CHECK_TYPES`, always-extract). Now it
  field-extracts on upload, and `doc_match_verdict` HOLDS an unread/blank file (`pending` /
  `unreadable`) instead of accepting it.
- **#2 — `income_support_doc` got a read + verdict.** The one doc Check 2 explicitly requests
  for a declared informal income cleared the gap on mere PRESENCE — a blank image "proved" a
  wage. Added its extraction schema (name/nric/amount/period/issuer/kind), a special
  `doc_student_verdict` branch (it names the EARNER, not the student → no student name-match →
  no false red on a genuine employer letter), and tightened
  `income_engine.has_income_support_doc` to require a real read (`student_verdict == 'ok'`).
  A blank/wrong image no longer clears `declared_income_gaps`; the Action-Centre upload of one
  is held for re-upload. New officer chip via `support_doc_check`.
- **F2/F3 — model doc-requests are member-tagged.** `check2_queries.sync_check2_queries` now
  writes `params={'household_member': spec['member']}` for the per-member proof codes, matching
  what officer requests already did and what the FE (`ActionCentre.tsx`) already forwards. This
  closes the salary-route hole where a model request landed BLANK-tagged (never counting as that
  member's evidence, yet auto-resolving by doc_type).
- **F3 — label honesty.** Base `parent_ic` cockpit label renamed "Earner's IC" → "Family
  member's IC" (en/ms/ta). The derived member ("Mother's IC" …) still renders whenever the
  stored tag or STR-route earner provides it; this only fixes the genuinely-unknown fallback.

## What Went Well

- **Verifying the "before" against the code, not the roadmap's baseline, saved real work.**
  The roadmap (written against an earlier tree) implied guardianship's verdict/resolution/chip
  needed building. Reading the actual code showed they *existed* — the only true gap was the
  extraction trigger. Scope shrank to one `frozenset` membership + a hold-on-unread branch,
  exactly as lessons.md warns ("verify feature state against the running system, not a summary").
- **The single income seam held again.** `has_income_support_doc` was the one funnel for the
  declared-evidence rule, so tightening it (presence → real read) fixed the verdict, the Check-2
  auto-resolve, AND the gap detector at once — no scattering.
- **No migration.** Everything rode existing columns/choices; the deploy is code-only, no
  migrate-first, low blast radius.

## What Went Wrong

1. **Four existing tests encoded the very bug being fixed.** `has_income_support_doc`'s
   presence-only behaviour was pinned green by tests that created a blank/field-less
   `income_support_doc` and asserted it cleared the gap / accepted the declared income.
   - *Root cause:* when the original 2A feature shipped "mere presence clears it", its tests
     baked that in — so the tests passed *because* the bug existed.
   - *Fix:* updated those four to model a REAL read (`student_verdict='ok'`) and added blank-doc
     (`wrong_doc`) companions asserting the gap PERSISTS. **System note:** when you tighten a
     "counts as evidence" rule, the tests that made the loose version pass are exactly the ones
     that must flip to assert the new failure case — grep for the helper that builds the doc and
     seed the verdict explicitly.

2. **A test used the newly-fixed doc type as its "unsupported" example.**
   `test_admin_rerun_vision_rejects_unsupported_type` used `guardianship_letter` to prove the
   re-run-vision endpoint 400s on a type with no automatic check. V1 gave it a check, so it
   started 200-ing.
   - *Root cause:* the test hard-coded a specific type as a stand-in for "unsupported" — a moving
     target.
   - *Fix:* switched the example to `photo` (genuinely unsupported). **System note:** a negative
     test that needs "an item NOT in set X" should pick one that is structurally outside X (a
     photo), not one that merely happens to be outside X today.

## Design Decisions

Logged in `docs/decisions.md` (V1 block): (a) `income_support_doc` verdict does NOT name-match
against the student (it names the earner) — the READ is the signal, so a blank fails but a
genuine parent's employer letter never false-reds; (b) an unread/blank guardianship or support
doc HOLDS the Action-Centre task (`pending`/`unreadable`) rather than accepting — the reviewer
is the backstop, and holding an unverified doc is safer than greenlighting it.

## V1.4 prod backfill (F3) — ✅ DONE (via claude.ai Supabase MCP, 2026-07-03)

The one-off attribution of the blank-tagged income docs on `applicant_documents` ran in the
claude.ai-connected session (this CLI agent's tool registry had no Supabase MCP). Results:
- **24 of 29** blank-tagged income docs attributed: **19 → mother, 5 → father**.
- **Refinement:** request-keyed docs were EXCLUDED from the earner auto-attribution and resolved
  from their officer item instead (app-75's request-keyed slip → father per the officer's prompt
  text) — the right call, since a request-keyed doc carries its own member intent.
- **5 rows deliberately left blank as ambiguous, for the owner:** **app 88 (×4)** — no earner and
  no working members on file; **app 16 (×1)** — guardian-earner vs a brother-member (a test
  account).
- Final income-doc tag distribution: **145 mother / 76 father / 2 brother / 5 blank**.

Pure residue cleanup — it did not gate the code deploy (V1.3 stops NEW blanks; V1.4 cleaned OLD
ones). **CARRY:** the 5 ambiguous rows above are for the owner to attribute or ignore (app 16 is
a test account).

## Deferred / follow-up

- **Existing `income_support_doc` rows** uploaded before V1 have no `student_verdict` → they now
  read as "not yet evidence" until re-run/re-uploaded (self-healing: Check 2 re-asks). Expected
  to be ~0–2 on prod; confirm during a re-run pass.

## Numbers

- 4 findings closed (#1, #2, F2, F3); 0 migrations; ~9 files (backend 6, frontend 5, i18n 3).
- +6 net scholarship tests (regression per finding: guardianship hold/pending/ok, income_support
  blank-doesn't-clear ×3, member-tag param, wiring assertions). 2025 pytest + 412 jest.
