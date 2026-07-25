# Retrospective — Institution must-fill, Sprint 1 (2026-07-25)

**Deliverable.** `chosen_programme.institution` gets its own writer, hoisted above every pathway
guard, plus a by-cause audit command. Backend only, no migration, nothing verdict/award/payment
touching. Roadmap `docs/plans/2026-07-25-institution-must-fill-roadmap.md`.

## What triggered it

Owner live review of #48: the Academic box showed a ticked Chosen Programme and a ticked Reporting
Date beside `Institution —`, and asked "why is the institution not filled even though the system
knows where the student attends?"

It knew twice over. The offer letter on file reads institution "UTHM - KAMPUS (CAWANGAN PAGOH)",
issuer "Universiti Tun Hussein Onn Malaysia", scored a genuine `ua_offer` at p=1.00. And the
catalogue lists the student's own declared course (UB4213001, Diploma Teknologi Animasi) at exactly
one campus: Universiti Tun Hussein Onn Malaysia. Neither was read.

## What was actually wrong — three layers

1. **The apply-form picker never records an institution.** `lib/scholarship.ts` stores
   `{course_id, course_name, field_key}`. Defensible (it is a programme list; a multi-campus poly
   course has no single campus to pick) but it means the field starts life blank for every
   student-made pick — and all 39 live blanks carry no `source` key, i.e. every one is a student pick.
2. **The one writer that fills it sat below four guards.** `autofill_pathway_from_offer` returns early
   on a name/IC mismatch, on junk in both slots, and on a genuine pathway clash. #48's offer OCR read
   the name as "LAKSMITHAA" for "LAKSMITHA" (a doubled letter) on 2026-07-07, so the function returned
   at the first guard. The doubled-letter tolerance shipped the NEXT day; the function has never
   re-run.
3. **`catalogue_institution` refuses to answer without a hint** — correctly, since its job is ironing
   out OCR variants and a hint-less match over an STPM bidang's ~250 schools would pick a wrong one.
   But that left the one unambiguous case (a course with a single campus) unserved.

## The uncomfortable finding

This is the **same bug the 2026-07-23 reporting-date sprint fixed**, one fact lower in the same
function. That sprint hoisted `sync_reporting_date_from_offer` above the guards, wrote the shape up as
a general lesson ("a fact riding as a passenger in a function whose real job is something else
inherits every one of that function's exits"), and left the institution sitting in the identical
position. The result is visible on #48's own screen: a ticked date beside an empty institution — the
hoisted passenger and the one left behind, side by side.

The lesson was correct and still didn't transfer, because it was written as a description of the bug
rather than as an instruction to go and check the neighbours. `lessons.md` now carries the sharper
form: when you hoist one passenger out, enumerate every other write in that function's tail.

## What we changed

- **`services.sync_institution_from_catalogue`** — the institution's own writer, called
  unconditionally above the guards, mirroring its reporting-date sibling. Sole-campus → the
  catalogue; multi-campus → the letter's campus validated against the course's campus list; matric →
  the catalogue college for the declared state. Never overwrites; touches only the `institution`
  sub-key so nothing is re-attributed to a letter.
- **`offer_pathway.sole_catalogue_institution`** — the hint-less answer, strictly `count == 1`.
- **`offer_pathway.offer_contradicts_course_institution`** — see below.
- **The tail block split in two.** It had been doing *fill a blank* and *normalise a drifted value to
  the catalogue's canonical spelling*. Hoisting the whole thing deleted the second job; a pre-existing
  test (`test_institution_aligned_to_catalogue_even_when_locked`) caught it. Normalising stays in the
  tail (it legitimately needs the freshly-written course_id); filling moved up.
- **`backfill_institution`** — report-only by default, groups every remaining blank by cause. Its own
  command because `backfill_offer_pathways` scans only offer-holders, and the sole-campus fill serves
  exactly the students who have uploaded nothing.

## The near-miss worth recording

The contradiction guard's first cut was `if not catalogue_institution(cid, offer_inst)`. That function
answers "can I verify these are the same place?", and its `''` means *unverifiable* as often as
*contradictory* — so it rejected #48's own letter ("UTHM - KAMPUS (CAWANGAN PAGOH)" shares no
distinctive token with "Universiti Tun Hussein Onn Malaysia"). The guard written to protect the field
would have blocked the single record the sprint existed to fix.

It surfaced because the test used the real prod string rather than an invented "UTHM". The fix is a
purpose-built predicate checking identity three ways — distinctive tokens, parenthetical-stripped
name, and the catalogue **acronym** — which separates #48 (acronym matches → same place) from #11's
Politeknik Ungku Omar against a UPNM asasi (nothing matches → a human decides).

## Verification

- **29 new tests**, `test_institution_fill.py`. Every one of the five `autofill_pathway_from_offer`
  exits is asserted separately — deliberately, because the reporting-date bug survived a test that
  pinned only the LOCK guard.
- The five guard tests were **run against the un-hoisted placement and confirmed to fail**, then pass
  with the hoist. The locked-pick test passes either way, correctly: the tail call already covered it.
- **4559 pytest** (full backend, up from 4523) + 746 jest, all green, `makemigrations --check` clean, no migration.
- Prod classification re-run read-only after the contradiction guard landed, confirming #48 fills and
  the 5 clash rows abstain.

## Carried

- **The data pass is owner-gated and NOT run** — the code is deployed, only the backfill waits. 11
  existing rows are fillable (8 live — #16 #42 #48 #49 #74 #97 #122 #145; 3 rejected — #7 #40 #139).
  It writes a sponsor-facing field on live records, so it needs an explicit go.
- Sprint 2 (QC gate + reviewer entry box, absolute per owner D1) and Sprint 3 (sponsor hyperlink,
  middot punctuation per D2, catalogue rows for #132/#136).
- 2 STPM rows (#94 #144) and 5 clashes stay human decisions by design; 7 rows have no course pick at
  all and nothing to fill from.

## Folded in

The officer Blockers card no longer renders at "Awaiting review" — a submitted student is past the
submission gate, so it could only read "Nothing outstanding" (owner). And `test_email_branding.py`
read its golden fixture in the platform encoding, which made the suite red on any Windows dev box;
pinned to UTF-8. Both unrelated to the sprint's deliverable, both cheap, both were in the way.
