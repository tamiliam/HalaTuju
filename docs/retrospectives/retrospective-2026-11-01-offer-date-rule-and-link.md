# Retrospective — Offer date rule, offer link and the campus test (2026-11-01)

Live: main `9969c1f3`, api-01225-fxd (no migration, no web build). Both repairs applied on live 2026-11-01 (owner yes).
Follow-up to `retrospective-2026-11-01-offer-realignment.md`.

## What Was Built

- **Offer link** (`services/offer_link.py`, `link_offer_courses`): an offer-sourced pick with labels only (#243,
  "Sarjana Muda Seni Halus" at "KOLEJ SEROJA, UNIVERSITI TEKNOLOGI MARA") gets its catalogue course id, catalogue
  name and campus; the source is kept. A new confirm now links too (`_settle_stale_course_id` → `pinned_match`).
- **The date rule** (owner): `PICKER_COMPLETE_AT` = 2026-10-31 13:10:21 MYT, the deploy of the complete scholarship
  picker. A pick on an application submitted before it, whose profile was not saved since, gives way to the
  student's own genuine offer — any course. Every realign guard kept; a profile saved since → `may_have_repicked`.
- **One campus test** (`offer_course_match.CampusReader`), shared by the matcher, `letter_place`,
  `institution_agreement` and `offer_contradicts_course_institution`; exact level check (`letter_level` vs
  `course_level`). Fixed #168's false Institution tick ("…, UMS Kota Kinabalu" had named Politeknik Kota Kinabalu).
- Live: 27 realigned (all `old_pick`), 9 linked.

## What Went Well

- The owner's #168 screenshot exposed the same fault class (place words naming an institution) in the tick that
  round 1 had found in the matcher; the fix became one shared definition instead of a second patch.
- Every dry run on live strings matched the live report exactly; the reviewer's sweeps (165 poly/KK/IPG campuses ×
  six name forms) measured losses and gains instead of guessing.

## What Went Wrong

1. **The first campus rewrite (whole-table "unique word") lost true matches and could flip on an unrelated row.**
   Symptom: round 3 found "UNIVERSITI TUN HUSSEIN ONN", "UNIVERSITI MALAYSIA PAHANG" and two polytechnic short forms
   reading `unknown` (and blocking the sponsor-facing institution fill), and adding a school row "SMK Sultan Azlan
   Shah" removed a polytechnic's tick. Root cause: a rule judged against the WHOLE institution table (≈800 schools)
   makes every answer depend on rows that have nothing to do with the letter. Fix: judge a campus only against
   itself (own name, unique acronym, explicit aliases, own non-place words) plus the stable "names another
   institution outright" guard; lesson below.
2. **Level families hid real level differences.** Symptom: round 4 found a "SIJIL" or "DIPLOMA LANJUTAN" letter
   pinning a plain Diploma course, because `detect_pathway_type` folds them into "diploma". Root cause: a coarse
   family built for pathway TYPE was reused as a course LEVEL check. Fix: compare the course's own `level` field
   exactly (`letter_level` / `course_level`).
3. **I wrote "28 October" to the owner as the cut-off before checking the deploy record.** Symptom: the builder
   measured the real cut-off from Cloud Build (2026-10-31 13:10 MYT) and my "~09:35" build was a different commit.
   Root cause: a date taken from memory of the decision log, not from the deploy that made the picker complete.
   Fix: a rule keyed on "when X went live" reads the build record before the number is shown to the owner.

## Design Decisions

- Date rule over an Islamic-course flag (owner option 1): the catalogue showed UM Muamalat needs no Islamic subject,
  so a flag rule could not reach #199; the date rule follows the owner's reason (the picker was incomplete).
- `StudentProfile.updated_at` as the "re-picked" signal: over-cautious (any profile save counts) but safe — a
  system write uses field-limited saves and never bumps it.
- Link keeps the source; realign runs before link in any combined run so the result does not depend on order.

## Code review / bite checks

Rounds 3, 4 and 5 of the adversarial review; every finding fixed or logged (TD-451 short forms crossing institution
type, TD-452 hand-written town list). Each fix bite-checked by disabling it alone; two silent bites got new tests.

## Numbers

- pytest (`-n auto`): 11,364 passed / 3 skipped on the rebased branch before push.
- Query cost of one offer check: #168 shape 8 → 6 queries, UiTM letter 9 → 8 (test-sized catalogue).
- Live: realign 27, link 9; skips listed in the CHANGELOG entry.
