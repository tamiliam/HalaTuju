# Retrospective — PISMP catalogue reconciliation + Aliran facet + MBPK gate (2026-06-18)

**Sprint 1 of the PISMP pathway work.** Commits `4446c2e` (bug fix + Aliran facet), `4589a6a` (req_disability gate).
Courses migration `0058`. All deployed and live.

## What Was Built

1. **Fixed the "0 of 0" Explore bug.** `CourseSearchView` treated `level=Ijazah Sarjana Muda` as STPM-entry-only and
   skipped the SPM branch, so PISMP (IPG teacher-training degrees) returned nothing. Now the SPM branch is skipped only
   for `source_type='ua'` (genuine STPM-entry degrees). Regression tests pin it.
2. **Aliran (school-type) facet for PISMP in Explore.** New read-time parser `apps/courses/pismp_taxonomy.py`
   (`aliran_of`, `is_elektif`, `classify_pismp`, `ALIRAN_VALUES/LABELS`) derives aliran (SK/SJKC/SJKT/SKPK) from the
   course-name suffix or `course_id` 6th char — no schema change. Search response gained `aliran`/`is_elektif` per
   course + an `alirans` filter block; the web search page shows an Aliran dropdown (visible only when
   source-type=PISMP), trilingual.
3. **SPM Perdana catalogue reconciled to the official 2026 guide** — every Perdana DB course now matches a PDF course by
   **code, name, requirements**: SJKT 10, SK 14, SJKC 15. Included a systematic `A→A−` requirement correction across all
   35 Perdana, the B/D/L→`…H` Pendidikan Khas/Prasekolah swap, and retirement of spurious/legacy rows.
4. **MBPK (special-needs) intake, disability-gated.** New `req_disability` must-HAVE flag on `course_requirements`
   (migration `0058`) + an engine gate (the inverse of the existing `no_disability` exclusion); 10 Laluan Khas track-A
   `50BK…` bidang ingested across SK/SJKC/SJKT, recommended only to students who declared a disability at onboarding.

## What Went Well

- **Migrate-first held.** The one schema change (`req_disability`) was applied to Supabase + the `django_migrations` row
  recorded *before* the code deploy — no boot-time column-missing crash.
- **Everything destructive was backed up.** Every retired row was exported to `Downloads/*_retire_backup_2026-06-18.json`
  before deletion, so the whole cleanup is reversible.
- **The owner's domain knowledge drove the right calls** — the "students select the course, so it must exist" framing
  settled the B/D/L→H swap, and the "we already collect disability, make it a requirement" insight gave MBPK a real
  eligibility gate instead of a browse-only badge.

## What Went Wrong

1. **MBPK first verification falsely failed — a boot-vs-insert race.** *Symptom:* after inserting the 10 MBPK rows, the
   live check showed a disability student as NOT eligible. *Root cause:* eligibility reads a pandas `requirements_df`
   cached **once at app boot** (`apps.py:61`); the revision serving traffic had booted *before* the insert, so its cache
   had no MBPK rows. *Fix / system change:* documented the rule in CLAUDE.md Next Sprint + the catalogue memory — **after
   any `course_requirements` data change, force an api restart** (`--update-env-vars=PISMP_DATA_RELOAD=<v>`, no rebuild)
   and re-verify against the *new* revision id, not just "after the insert".
2. **A generated requirement was mathematically impossible (caught in review).** *Symptom:* the SJKC Bahasa Melayu
   C-group was generated as `min_count:4` over only 3 subjects — un-satisfiable. *Root cause:* the group-builder didn't
   sanity-check count ≤ available-subjects. *Fix:* corrected the row and added a count ≤ subjects sanity assertion to the
   generation step so an impossible group can't be written again.
3. **I twice assumed "junk" where there was signal.** *Symptom:* I flagged `…041S004` as a duplicate to delete and the
   B/D/L rows as low-value — both wrong on first pass (the owner: "P is correct and 4 is wrong"; and the B/D/L rows had
   bespoke Braille/BIM/autism descriptions worth preserving). *Root cause:* treating a surprising row as an error before
   reading it fully / checking it against the source. *Fix / lesson:* before retiring a "spurious-looking" catalogue
   row, read its content and check it against the PDF index — surface the trade-off to the owner rather than deleting on
   assumption. (Captured in lessons.md.)
4. **I asserted a code change was needed when it wasn't.** *Symptom:* I claimed Tier-2 requirements needed an engine
   change to support student-key subjects. *Root cause:* I forgot `map_subject_code`'s lowercase fallback already passes
   unknown codes straight through to the student grade key. *Fix:* verified the actual code path before claiming a change
   is required — the Tier-2 requirements went in as pure data.

## Design Decisions

- **Aliran is derived (read-time), laluan would earn a column.** Aliran only affects display/filtering, so it stays a
  pure `pismp_taxonomy.py` derivation. (Laluan, which *gates eligibility*, is specced to earn a real column in the
  deferred STPM sprint — see `memory/halatuju-pismp-refresh-spec.md`.)
- **MBPK gated on the existing "Physical disability" signal, accepting it's a partial proxy.** Reuses onboarding data the
  student already provides rather than adding a new field; knowingly under-captures non-physical MBPK (learning/hearing/
  visual). Revisit by broadening the Special-Needs field if MBPK matching proves too narrow. (See decisions.md.)
- **B/D/L→H swap chosen despite losing bespoke descriptions.** The B/D/L rows had richer copy but their requirements were
  un-satisfiable AND they weren't the courses students actually select; correctness + selectability won over copy
  quality. The new `…H` rows carry cloned generic descriptions (logged as deferred polish).

## Numbers

- 2 code commits to `main` (`4446c2e`, `4589a6a`); 1 migration (`courses/0058`).
- Catalogue: SJKT 10 + SK 14 + SJKC 15 Perdana reconciled; 10 MBPK ingested (270 offerings).
- ~28 rows retired (all backed up).
- New tests: `test_pismp_taxonomy.py`, `TestUnifiedSearchPismpLevelFilter`, `TestUnifiedSearchPismpAliranFilter`,
  `test_req_disability.py` (3). 105 courses tests green.
- 2 api revisions to verify data changes (…00446 race → …00447 verified).
