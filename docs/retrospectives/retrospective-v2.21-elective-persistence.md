# Retrospective — v2.21.0: Elective subjects persist + cap raised 2 → 7

**Date:** 2026-05-31
**Version:** 2.21.0
**Migration:** `courses/0052` (additive — `StudentProfile.elective_subjects`), applied migrate-first via Supabase MCP **to `api_student_profiles`** (see the db_table incident below).

Started from a bug the user found: SPM electives vanish on logout/login. Investigation showed electives had no durable identity, and the fix paired naturally with a requested feature — raise the elective cap from 2 to 7 (high achievers sit many subjects; 11-A cases exist).

## What Was Built

- **`StudentProfile.elective_subjects` JSONField** — the durable record of *which* grade keys are electives, mirroring `stream_subjects` (TD-063). Synced in `/profile/sync/`, returned by the profile GET.
- **Login re-hydration** — `auth-context` now restores `KEY_ELEKTIF` (from `elective_subjects`) *and* `KEY_ALIRAN` (from `stream_subjects`), so the grades form rebuilds the full selection after a logout/login. This also fixes the latent aliran case (previously masked by a stream-default fallback).
- **Cap 2 → 7** via a single `MAX_SPM_ELECTIVES` constant. The merit engine is unchanged — Sec3 still scores the best 2 electives — so the golden master is untouched; more electives just enlarge the pool, which *improves* accuracy for high achievers and avoids wrongly-ineligible cases.

## What Went Well

- **Bug + feature were genuinely one change.** Raising the cap to 7 is pointless without durable storage (the extras would vanish on login anyway), and the new field is a list that holds 2 or 7 identically — so building it once for N was cleaner than two passes. The investigate-first step established that before any code.
- **The engine needed no touching.** Confirming `prepare_merit_inputs` does `remaining.sort()[:2]` (best-2, count-invariant) up front meant zero risk to the SACRED golden master — verified, 5319 intact.
- **The investigation prevented two wrong builds.** Reading the merit engine first ruled out an engine change; reading the STPM flow first revealed it's a separate subsystem (avoiding a half-fix); the backfill dry-run revealed it couldn't be done cleanly *before* I ran a destructive UPDATE.

## What Went Wrong

1. **The migrate-first `ALTER` hit the wrong table — the exact `db_table` trap that's already in lessons.md.**
   - *Symptom:* my first `ALTER TABLE student_profiles ADD COLUMN elective_subjects` succeeded against a 30-row legacy table; the live 617-row table (`api_student_profiles`) didn't get the column.
   - *Root cause:* I wrote the raw SQL from the table name I assumed (`student_profiles`) instead of reading `StudentProfile.Meta.db_table` first — despite this being a standing lessons.md entry *and* a logged tech-debt item (TD-025: an `api_` prefix exists precisely because a legacy `student_profiles` table also exists). The two same-purpose-looking tables are a footgun and I stepped on it.
   - *What caught it:* I verified the column landed by querying the schema, noticed `stream_subjects` was absent from the table I'd altered (a real `api_student_profiles` would have it), and traced it to `Meta.db_table`. Corrected: added the column to `api_student_profiles`, dropped the erroneous one from `student_profiles`, re-verified. Had I trusted the "success" and pushed, prod would have 500'd on the missing column.
   - *System change:* TD-025 bumped Low → **Medium** with the incident recorded; the `db_table='api_student_profiles'` gotcha is now called out in `halatuju_api/CLAUDE.md` so the next raw/MCP `ALTER` sees it. Real fix (drop the legacy table) tracked in TD-025.

2. **The historical backfill couldn't be done — found at the dry-run, not after a bad write.**
   - *Symptom:* I intended to backfill existing electives by deriving `grades − core − stream_subjects`; the dry-run showed 485 of 491 profiles have empty `stream_subjects`, so the derivation would mislabel stream subjects (phy/chem/…) as electives.
   - *Root cause:* `stream_subjects` only landed in v2.13.0 (TD-063), so almost no historical profile has it — without it, stream vs elective is genuinely indistinguishable.
   - *What prevented harm:* dry-run-SELECT-before-UPDATE. I skipped the backfill entirely (mislabeling is worse than empty; nothing in the DB is deleted; the fix prevents all future loss). Reinforces: always dry-run a data migration's SELECT before its UPDATE.

## Design Decisions

Logged in `docs/decisions.md`:
- **Explicit `elective_subjects` field** (the user's "option 1") over derive-on-reload — records intent even for a subject entered without a grade, and is unambiguous at 7 electives.
- **No historical backfill** — derivation can't separate stream from elective for 485/491 profiles; forward-fix only.
- **STPM flow left untouched** — separate subsystem; mirroring it is TD-069 (user: "don't touch STPM").

## Numbers

- **Backend:** 1396 pytest (+7). 0 failures. **Golden master 5319 intact** (no engine change).
- **Frontend:** 171 jest; `next build` clean.
- **Migration:** `courses/0052` additive, migrate-first (to `api_student_profiles`).
- **Backfill:** none (by decision); 0 rows mutated.

## Carried Forward

- **TD-069** — STPM-flow SPM electives (same fix, separate field) when wanted.
- **TD-025** — drop the legacy `student_profiles` table to remove the footgun for good.
- **Live-verify** — enter >2 electives, log out/in, confirm they survive; confirm merit/eligibility unchanged.
- Existing students' pre-fix electives aren't auto-restorable; they repopulate on next onboarding save.
