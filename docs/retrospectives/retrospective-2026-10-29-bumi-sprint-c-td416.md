# Retrospective — Bumi coverage Sprint C (Islamic SPM subjects) + TD-416 (message slices) — 2026-10-29

Shipped together in one deploy on the owner's ruling ("2"): `main` `1a4aedc8`, api-01174-4cp, web-01008-hdx,
both builds SUCCESS. TD-416 closed in the register by `caa74b4e` (docs only, no build).

## What Was Built

- **TD-416** (`f1ae0a83`): the `scholarship` and `sponsor*` namespaces left the core English catalogue as two
  page-loaded slices on the TD-360 pattern. First-load median 179.957 -> 146.378 kB. The ratchet TIGHTENED:
  median line 180 -> 148, three per-route lines 4 kB lower. `sliceReach.test.ts` extended.
- **Sprint C** (`9d1dedca`, review fixes `5a4e186e`, `f4aa714d`, `1a4aedc8`): the 13 Islamic-studies SPM subjects
  are electives on the SPM grades form and the STPM page's SPM block, under their result-slip names. Old stored
  short names are aliases (no re-read). Slip and certificate readers tolerate apostrophe, "&" and spaced-hyphen
  forms. `MODEL_VERSION` 1.18.0. A subject counts once per SPM prerequisite group (owner ruling), by maximum
  matching. STPM golden master 2,026 -> 2,025 on purpose; SPM 5,319 unchanged. No migration.

## What Went Well

- **Taking weight off, not raising the line.** TD-416 named both honest options; the first one won 33.6 kB and
  let the ratchet tighten. The Billing session's merged tree went from 0.042 kB of room to 1.6 kB with no
  problem line — the cliff that every sprint had paid for separately is gone.
- **Three adversarial review rounds each found something real** (old stored names; double counting; looser
  printing). None reached production.
- **Impact counted before changing a reader:** 18 of 2,313 live reads carry an Islamic name; at most 15 rows on
  2 documents could move from the code/band tolerance. That turned "do we need a re-read?" into a number.
- **Cross-session coordination held.** Billing, Request and this session pushed to main within hours of each
  other with no lost work; each merged the other's tree and re-ran the budget before pushing.

## What Went Wrong

1. **The builder's "count once" fix was first-fit, so list ORDER could waste a subject.**
   *What:* the dedupe gave each code the first free student key; with `BAHASA_ARAB_MUASIRAH_SPM` listed before
   `BAHASA_ARAB_SPM`, `bahasa_arab` was spent on the first code and a student holding both Arabic subjects
   counted 1, not 2. *Why:* "each subject counts once" over a many-to-many code->key map is an assignment
   problem; a greedy loop looks right and passes every test whose list happens to be in the kind order. The
   brief stated the rule but not that order must not matter. *Fix:* `_distinct_matches` (maximum bipartite
   matching) plus `test_list_order_cannot_waste_a_subject`, which puts the list in the unkind order. Lesson
   added to `docs/lessons.md`.
2. **The first slip-name change would have orphaned every stored read with an old short name.**
   *What:* review #1 (HIGH) found that renaming "Manahij" etc. to slip wording made the 18 stored reads stop
   matching. *Why:* the change was reasoned about from the form side (what a student types) and not from the
   data side (what is already stored). *Fix:* `_SUBJECT_ALIASES` keep the old names; the same shape is already in
   `lessons.md` as the expand-contract rule for renaming a stored value (keep the old one tolerated) — the
   brief did not point the builder at it. Future briefs that rename a recognised name cite that lesson.
3. **A rebase used an inline variable (`GIT_EDITOR=true git rebase --continue`).** *Why:* habit. *Fix:*
   `git -c core.editor=true rebase --continue` is the allowlist-safe form; already in the Bash hygiene rule.
4. **A docs-only push was watched for builds that never start.** *Why:* the triggers ignore `docs/**` and
   `halatuju_api/CLAUDE.md`; a watcher keyed on "a build for this SHA exists" waits forever. *Fix:* before
   watching, check whether the push touched `halatuju_api/**` or `halatuju-web/**` at all.

## Design Decisions

- Islamic subjects are ordinary electives, not a stream, so merit pools do not move (decisions.md, 2026-10-29).
- A subject counts once per SPM prerequisite group (owner, decisions.md 2026-10-29); the count is a matching.
- `scholarship.nav`, `.subnav`, `.banner` stay in core because shared chrome reads them on most routes.
- Not done on purpose: `BA -> b_arab` (no fixture uses `BA`), `profile_engine._SUBJECT_GROUP`, `pathways.py`.

## Bite-checks (step 4b)

Both injected, both bit, both restored by original bytes with the digest checked:
- `_distinct_matches` reverted to first-fit -> `test_list_order_cannot_waste_a_subject` FAILS.
- `/scholarship/apply` page loses its `messagesScholarship` import -> `sliceReach.test.ts` FAILS (2 tests).

## Numbers

- 9,719 pytest / 3 skipped · 4,767 jest / 303 suites, on `1a4aedc8`; the deploy gate's own `pytest -n auto` run
  passed in Cloud Build.
- Golden masters: SPM 5,319 · STPM 2,025.
- Bundle: median 146.378 kB / 148, 1.6 kB room, 1 route may cross first.
- Time (commit clock): TD-416 ~0.5 h; Sprint C ~1.3 h build + reviews; rebase, re-gate and deploy ~1 h, shared.
  Planned: no hour figure (roadmap size "medium").

## Follow-ups

- `scholarship/award/page.tsx` is at 717/717 lines: split before its next change.
- `SPM_PREREQ_OPTIONAL` is dead code; `profile_engine._SUBJECT_GROUP` lacks the Islamic keys.
- Link prefetch fetches the slice chunks in the background for Malay/Tamil readers (off the first-load path).
- NEXT in the arc: Sprint D — SPM catalogue Bumi + Islamic course ingest (`req_bumiputera` on
  CourseRequirement), with an adversarial review before push.
