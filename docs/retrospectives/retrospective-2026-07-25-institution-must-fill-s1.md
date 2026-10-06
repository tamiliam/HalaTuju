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
   on a name/IC mismatch, on junk in both slots, and on a genuine pathway clash. On 2026-07-07 #48's
   offer OCR read the name as "LAKSMITHAA" for "LAKSMITHA" (a doubled letter) and the function returned
   at the first guard. **CORRECTION (added 2026-07-25, after the owner challenged the diagnosis):
   that guard no longer fires.** The doubled-letter tolerance shipped 2026-07-08 and `_name_status`
   recomputes live, so `chk['name']` reads `match` today (the IC guard reads `unreadable`, not
   `mismatch`, so it doesn't fire either). I had read the STORED `student_verdict: 'name_mismatch'`
   from 7 July and concluded the guard was blocking, without checking that the value is derived, not
   trusted. The hoist is therefore DEFENSIVE — it protects the fill when a guard genuinely fires (a
   real wrong-person letter, junk slots, a true pathway clash) — and was not what unblocked #48.
3. **`catalogue_institution` refuses to answer without a hint** — correctly, since its job is ironing
   out OCR variants and a hint-less match over an STPM bidang's ~250 schools would pick a wrong one.
   But that left the one unambiguous case (a course with a single campus) unserved. **This is the
   load-bearing cause.** Even with every guard passing, the old code could not fill #48: the hint
   available is the letter's "UTHM - KAMPUS (CAWANGAN PAGOH)", whose distinctive tokens
   ({uthm, kampus, pagoh}) share nothing with the catalogue's "Universiti Tun Hussein Onn Malaysia"
   ({tun, hussein, onn}), and the normalised names aren't equal either — so it returns ''.
   `sole_catalogue_institution` is what actually fills #48 and the other 10 rows; nothing else in the
   system produces that value.

## The uncomfortable finding

The institution sat in the **same position** the reporting date had occupied before 2026-07-23 — one
fact lower in the same function, below the same guards. (The guards were not what cost #48 its
institution; see the correction above. The structural point stands: an independent fact was riding as
a passenger in a function whose job is something else, and inherited its exits.) That sprint hoisted `sync_reporting_date_from_offer` above the guards, wrote the shape up as
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


---

# Addendum — the regression this sprint caused (2026-07-26)

Within hours of the deploy the owner re-ran #48's offer letter and the record broke. This section is
part of the same retrospective because the incident is not separable from the sprint: it is what the
sprint's own change did on contact with a real document.

## What happened

The re-extraction itself went well — genuineness re-scored from a stale 1.4.0 to 1.6.0, still
`genuine`/`ua_offer` at p=1.00, `student_verdict` moved `name_mismatch` → `ok`, the reporting date
held. My writer fired and filled the institution with the catalogue's "Universiti Tun Hussein Onn
Malaysia": the intended outcome.

Then `offer_pathway_match` compared that recorded value against the letter's "UTHM - KAMPUS (CAWANGAN
PAGOH)" by distinctive-token overlap — `{tun, hussein, onn}` against `{uthm, kampus, pagoh}` — and
returned `clash`. A correct pathway read `mismatch`. Red Pathway chip, no Institution tick, one red
chip docked off the verdict band, and Check 2 raised a `pathway_confirm` asking the student to confirm
a pathway that was already right.

While the field was blank that comparison returned `unknown` — nothing to compare, benignly silent.
**Filling a field converted a silence into a false accusation.**

## Why (root cause, three layers)

1. **The tests covered the writer and nothing that consumes it.** 29 tests on
   `sync_institution_from_catalogue` — every guard, every resolution branch, idempotency, the
   contradiction abstain — and not one on what a reader does with a value it has never received. The
   transition blank→populated was expressed nowhere, so 4559 green tests said nothing about it.
2. **I created a divergence in the same sprint and only tested one half.** I taught
   `offer_contradicts_course_institution` that a catalogue ACRONYM identifies an institution —
   precisely because "UTHM" shares no token with the full name — then left `_field_status`, which
   paints the officer's chip and drives the verdict, comparing the same two strings by token overlap.
   Acronym-aware guard, acronym-blind display, hours apart, same pair of strings.
3. **I named the wrong cause for the original bug** and the fix inherited that error. I read #48's
   STORED `student_verdict: 'name_mismatch'` from 7 July and concluded the wrong-person guard was
   blocking the fill; in fact the name tolerance shipped 8 July and `_name_status` recomputes live, so
   the guard passes. Had I checked the live computation I would have found the real cause
   (`catalogue_institution` refusing a hint-less answer) first, and would have been looking at the
   acronym problem from the start — which is exactly what bit.

## What prevents recurrence

- **The invariant test**, which is the shape that would have caught it: *the pathway verdict is the
  same whether the institution is blank or filled*, for the same student and the same letter. Asserted
  across the transition, not about the new value. Verified to fail against the old comparator.
- **One shared predicate.** `_refers_to_campus` is now the single definition of "this string names
  this campus", used by the writer's guard, the Pathway chip and the Institution tick.
- **Two lessons** in `docs/lessons.md`: populating a previously-empty field is a change to every
  reader that has only ever seen it empty; and two functions answering the same question must share
  the predicate or the one you are not looking at stays wrong.

## What went right

The blast radius was one row. #48 was the only offer re-extracted after the deploy, because I had
held the 11-row backfill for owner approval rather than running it with the code. That single
judgement is the difference between one student's screen and eleven. It also argues for the habit:
ship the code, let it run on one real record, then backfill.

## Owner's contribution to the fix

The final design is the owner's, not mine. I was going to make the comparison acronym-aware — a
string heuristic that would have needed extending for "UTHM Pagoh", "Kampus Pagoh, UTHM", English and
Malay forms, campus codes. The owner's observation replaced it: *"The course selector only has one
option, UTHM. So there is a match."* For a single-campus course a clash is not unlikely, it is
impossible, so no string rule is required at all. Comparison is meaningful only for a multi-campus
course, where the catalogue supplies both the candidate set and the acronyms.
