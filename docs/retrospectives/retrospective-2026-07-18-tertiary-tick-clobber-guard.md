# Retrospective — Tertiary Institution tick + profile-sync clobber guard (2026-07-18)

Two owner-flagged follow-ups off the 2026-07-17/18 Academic-box redesign, done in one short
session. NO migration; web + api. Commits `e8db600c` (tick) / `8c3c7572` (guard).

## What Was Built

1. **Verified tick on the tertiary Institution row.** The unified Academic box ticks the
   Institution only for pre-U pathways (matric/STPM) via `institution_status` — offer institution
   vs `pre_u_institution`. A tertiary student (poly / UA diploma / asasi / PISMP) shows
   `chosen_programme.institution` and carries a blank `pre_u_institution`, so `institution_status`
   was always `unknown` and the row never ticked even with a genuine, matching offer on file.
   - Backend: `pathway_engine.student_offer_check` gains `chosen_institution_status` =
     `_field_status(chosen_programme.institution, offer institution)`.
   - FE: `fieldVerification.ts` gains a generic `institution` field that ticks on a usable genuine
     offer whose `chosen_institution_status === 'match'` AND `pathway !== 'mismatch'` (identical
     red-chip guard to `preUInstitution`). The cockpit picks `preUInstitution` for pre-U and the
     new `institution` tick for tertiary.

2. **Profile-sync clobber guard.** `family.copy_pathway` copied `chosen_programme` field-for-field
   from the profile onto the open application whenever any pathway field changed (the two-way
   sync in `ProfileView.patch`). A student editing an unrelated pre-U field with a blank profile
   `chosen_programme` therefore overwrote the app's offer/officer-confirmed programme with `{}`
   (the #117 case, previously patched by hand via MCP). `copy_pathway` now routes
   `chosen_programme` through `_should_overwrite_chosen_programme`: an empty value never overwrites
   a populated one, and a plain student-sourced value never overwrites a confirmed one
   (`offer_letter_auto`/`offer_letter_confirmed`/`repair_chosen_programme`/`officer_interview`).

## What Went Well

- The tertiary tick avoided the tempting-but-wrong shortcut of reusing `pathway === 'match'`:
  `_declared_pathway` deliberately ignores an `offer_letter_auto` chosen_programme, so a poly
  student whose institution was filled from the offer reads `pathway = 'unknown'` — the tick would
  never have fired. Reading the backend first exposed this before it shipped as a dead tick.
- The clobber fix is one guarded field in a shared helper; no caller change (the caller's
  `update_fields` save of the unchanged value is a harmless no-op) and the closed-status freeze is
  untouched.

## What Went Wrong

- **The full jest suite failed to spawn (environment, not code).** Symptom: `npx jest` across all
  suites died with `spawn UNKNOWN` on the 8 GB dev box. Root cause: memory pressure spinning up
  many workers at once (the same class as the documented `next build` OOM). Fix already in play:
  run the whole suite single-threaded (`--runInBand`) for the sprint-close count, and trust Cloud
  Build for the real gate. The targeted subsets ran clean throughout.

## Design Decisions

- **Provenance-guarded `chosen_programme` copy** (logged in `decisions.md`): a two-way field sync
  must not treat a derived/confirmed value the same as a student-typed one. Chose a per-field
  guard keyed on `chosen_programme.source` over splitting the sync into two field sets or freezing
  the sync earlier.
- **New backend field over reusing `institution_status`**: the pre-U comparison is anchored to
  `pre_u_institution` for a documented reason (#117); tertiary needed its own comparison against
  the shown `chosen_programme.institution`, so a distinct `chosen_institution_status` keeps the two
  ticks from ever contradicting each other.

## Numbers

- +3 backend tests (`chosen_institution_status`) + 4 (clobber guard) + 2 jest (tertiary tick).
- Targeted suites green: `test_pathway_engine` (40), `test_family` (+guard), `test_offer_pathway`
  / `test_confirm_pathway` / `test_verdict_engine` / `test_resolution` (258), courses
  pathway/profile (57), `fieldVerification.test.ts` (19).
- No migration. Deploy = push (owner-gated); api rebuild (pathway_engine + family) + web rebuild.
