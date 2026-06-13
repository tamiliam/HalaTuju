# Retrospective — Course-Data Pipeline Sprint 3 (2026-06-13)

Roadmap: `docs/roadmap-course-data-pipeline.md`. Post-SPM catalogue refresh via e-Panduan `jenprog=spm`.
**Re-scoped on discovery to "Sprint 3a" — the MOHE-coded (UA/Asasi) subset only** (owner-approved mid-sprint).

## What Was Built
- **Scraper parameterised for SPM** — `scrape_mohe_stpm` gained `--jenprog {stpm|spm}` (default `stpm`, behaviour
  unchanged), `--max-pages N` (for safe validation spikes), and SPM categories (`A`=current year default, `B`=past).
  The listing URL's `jenprog=` + the detail-URL suffix are now parameterised; extracted a pure `detail_url()` builder.
- **`Course.is_active`** (migration `0054`, additive) — implements the logged "deactivate, never hard-delete" decision
  for the SPM catalogue. **No read path filters on it yet** (deliberate — keeps the golden master untouched; wiring
  search/eligibility to exclude inactive is a clearly-scoped follow-on, mirroring how `StpmCourse` got there).
- **`sync_spm_mohe`** — mirrors `sync_stpm_mohe` but **restricted to the MOHE-coded subset** (`course_id` matching
  `^[A-Z]{2}[0-9]{7}$`, the UA/Asasi `U*` programmes). Reports new (never auto-adds), deactivates removed / reactivates
  returned (behind the same mass-deactivation guard), updates merit (→ `CourseRequirement.merit_cutoff`). The
  synthetic-ID catalogue (POLY-*/KKOM-*/TVET-*/PISMP) is **excluded from the comparison entirely** — never matched,
  never deactivated.
- Validated the parser on **live e-Panduan**: `--jenprog spm --category A --max-pages 1` → "Found 363 programmes",
  page 1 parsed 10/10 cleanly, all MOHE-coded `U*` Asasi codes, merit + `/A/spm` detail URLs correct.

## What Went Well
- **The scoping discovery happened BEFORE any code** — reading the model + one read-only prod query (id-scheme
  breakdown) surfaced that only 89/390 SPM courses carry MOHE-matchable IDs. Caught the trap that a naive whole-catalogue
  diff would flag ~300 courses as "removed" and trip the guard. Re-scoped with the owner instead of building the wrong thing.
- **The mass-deactivation guard earned its keep conceptually** — the restriction means it never even sees the synthetic
  IDs, but had the restriction been missed, the guard was the backstop. Defence in depth.
- **STPM behaviour stayed byte-identical** — all defaults unchanged; the existing `refresh_stpm` pipeline + docs untouched.
  1076 courses pytest (1047 baseline + 29 new), 0 failures, golden master intact (the additive field touches no read path).
- **Worktree isolation, third time, frictionless** — built in `.worktrees/spm-catalogue` alongside another active agent.

## What Went Wrong
- **The roadmap under-scoped Sprint 3** — it said "mirror `sync_stpm_mohe` over the SPM catalogue", assuming the SPM
  `Course` model had the same shape as `StpmCourse` (inline `is_active`/`merit_score`/`mohe_url`) and a uniform ID scheme.
  Neither held: SPM merit lives in `CourseRequirement`, URLs in `CourseInstitution`, there was no `is_active`, and IDs are
  a mix of MOHE codes + internal synthetic schemes.
  - *Root cause:* the 2026-06-12 spike validated the scrape **card structure** but never checked the **sync target** —
    the model shape or the ID provenance of the existing catalogue. "Same portal HTML" was mistaken for "same pipeline".
  - *Fix:* before scoping any "mirror/extend X" sync sprint, verify the target model's fields AND the ID provenance of
    the data being diffed — a cross-catalogue ID-scheme mismatch silently breaks a key-based diff. (Lesson added.)

## Design Decisions
- **Restrict the SPM sync to the MOHE-coded subset; defer the synthetic-ID crosswalk.** Logged in `decisions.md`. The
  ~300 Poly/KK/TVET/PISMP courses need a name+institution crosswalk (lesson-19 territory; false-merge risk into the
  golden-master eligibility data) — its own sprint (3b). New courses are reported, never auto-added (requirements parsing
  = Sprint 3c), same policy as STPM.
- **Add `is_active` but wire NO read-path filter this sprint.** Keeps blast radius minimal and the golden master provably
  untouched. The field is populated by the sync; hiding inactive courses from search is a separate, golden-master-adjacent change.

## Numbers
| Metric | Value |
|--------|-------|
| New tests | 29 (scraper params/URL ×11, is_mohe_coded ×11, sync restriction/guard/merit/new ×7) |
| Suite | 1076 courses pytest (was 1047), 0 failures; golden master intact |
| Deploys | 0 (ships on owner's next deploy — migration `0054` migrate-first, then merge) |
| Files | scraper + new sync command + 2 test files + migration + docs |
| Migration | `0054_course_is_active` (additive; NOT yet applied to prod) |
