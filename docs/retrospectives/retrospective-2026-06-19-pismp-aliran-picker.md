# Retrospective — PISMP Aliran → Bidang pathway picker (2026-06-19)

**Sprint 2 of the PISMP work** (Sprint 1 = catalogue reconciliation + Aliran facet + MBPK gate, 2026-06-18). Commits
`d86cf11` (picker) + `c321f7d` (live-review). No migration. Deployed; 2 deploys (initial + one live-review round).

## What Was Built

A student on the PISMP (teacher-training) pathway now reaches the exact course in **two taps** — pick the **school type**
(Aliran: SK/SJKC/SJKT/SKPK) then the **subject** (Bidang) — instead of a type-a-course-name box that assumed they knew
the course name.

- **Backend:** `EligibilityCheckView`'s eligible-courses payload now carries `aliran` for PISMP courses, derived via the
  existing `pismp_taxonomy.aliran_of` (no migration, serializer-only). Non-PISMP courses get an empty aliran.
- **Frontend:** new `AliranPicker` (eligible-only school-type chips) feeding the existing compact course combobox
  (`ProgrammePicker`, the same one the UA pathway uses). Pure helpers in `lib/scholarship.ts` — `pismpAlirans`,
  `bidangForAliran`, `aliranForChosen`. Wired into BOTH the shared `PathwayPicker` (/profile) and the inline `/apply`
  flow via the same components, so the two surfaces behave identically by construction.
- Trilingual en/ms/ta. Elektif (the minor) deferred.

## What Went Well

- **Stitch-first paid off.** The mock was approved before any template code; the build matched it. The one design change
  (compact combobox vs the first-cut vertical list) came from seeing it *live*, not from a coding dead-end.
- **Reused the existing combobox instead of a bespoke list.** The owner's "use the UA method" feedback let me delete the
  custom `BidangPicker` and feed `ProgrammePicker` the per-aliran courses — less code, identical UX to the rest of the
  form, and the lesson "reuse the same component both surfaces use" held.
- **"Verify before assuming a bug" worked.** When the owner asked why 4 SJKT subjects were missing, the answer was in the
  official PDF, not the code — the eligibility engine was correct. Checking the source PDF (Matematik needs both maths at
  A−; Jasmani's science pool excludes Physics/Chem) avoided a wrong "fix" that would have broken correct requirements.

## What Went Wrong

1. **The first-cut UI was a custom vertical list, not the established combobox.** *Symptom:* the owner's live-review asked
   to switch to "the UA method" (compact combobox). *Root cause:* I designed a new bidang list from the Stitch mock
   without first checking that the app already had a course-selection component (`ProgrammePicker`) used by every other
   programme pathway — so the mock diverged from the app's own convention. *Fix / lesson:* when prototyping a step that
   parallels an existing one, prototype *to the existing component's pattern*; check for a reusable picker before drawing
   a new list. (Captured in lessons.md.)
2. **A redundant "(Aliran Bahasa Tamil)" label surfaced only on the live app.** *Symptom:* the picker and the
   recommendation card read "… (SJKT) (Aliran Bahasa Tamil)". *Root cause:* `deduplicate_pismp` appends an "(Aliran …)"
   language descriptor — written for the *old* catalogue where names had no aliran suffix; after Sprint 1 added "(SJKT)"
   to every name, the append became double-labelling. My eligibility-side change didn't touch that legacy dedup, and it
   only shows for Tamil/Chinese-stream students (my synthetic all-A+ test student had no vernacular credit, so it never
   appeared in my probes). *Fix / lesson:* when a feature consumes an existing transform (here `deduplicate_pismp`),
   check what that transform does to the *new* data shape — and test with an input that actually exercises it (a student
   with a Bahasa Tamil credit), not just the convenient all-A+ case.
3. **node_modules isn't shared by git worktrees.** *Symptom:* jest/`next build` failed with "ts-jest not found" in the
   worktree. *Root cause:* worktrees share `.git` but not gitignored `node_modules`. *Fix:* a PowerShell directory
   junction to the primary checkout's `node_modules` (mklink from Git Bash silently no-op'd; `New-Item -ItemType
   Junction` worked). Noted for future worktree-based FE work.

## Design Decisions

- **`aliran` exposed on the payload (backend-derived), not re-derived in TypeScript.** Keeps the single authoritative
  aliran derivation in `pismp_taxonomy` (per Sprint 1's decision), avoids duplicating the suffix/id-digit logic + its
  MBPK edge cases in the frontend. Cost: a backend deploy alongside the web deploy (a small full-stack sprint, not pure
  FE). (See decisions.md.)
- **Replace the type-search box for PISMP, don't sit alongside it.** Owner's call — the browse is strictly easier and
  there's one code path. Other programme pathways keep `ProgrammePicker` directly.
- **Aliran chips are eligible-only (no dimmed "not for you" chip).** Mirrors `PathwaySelect`; a student only sees school
  types they have eligible courses for. (The Stitch mock showed a dimmed SKPK; dropped it as cleaner + honest.)

## Numbers

- 2 code commits (`d86cf11`, `c321f7d`); no migration.
- New: `AliranPicker.tsx`; helpers `pismpAlirans`/`bidangForAliran`/`aliranForChosen`; `aliran` on `EligibleCourse`.
  Removed the first-cut `BidangPicker.tsx`.
- Tests: +1 backend (`test_pismp_courses_carry_aliran`) + a no-`(Aliran)` assertion in `test_eligibility_service`; jest
  helper tests. `next build` clean; golden master intact.
- 2 deploys (initial + live-review). api `…00451`, web `…00444`.
