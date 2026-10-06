# Retrospective — a less specific answer is not a contradicting one (request #9), 2026-08-01

**Deliverable:** the officer's Programme and Institution ticks stopped rewarding records with
nothing on file and stopped punishing records that were right.

**Shipped:** `4d61658a` (the two predicates + 6 tests), `4706ab91` (the read-only audit),
`d9e83bda` (the guard narrowed after measuring), `ce3524cd` (docs). No migration. **Two deploys.**
`pytest` **5348**. 3.0h estimated / 3.0h spent.

---

## What was wrong

BrightPath reported that four PISMP students who had answered every question had **no** Programme or
Institution tick, while the one student who had answered **nothing** had both. They read it as the
same family as #7/#8 — correctly — and the cause turned out to be the exact inverse of the symptom.

The tick has two conditions: the institution must agree with the letter, **and** the pathway chip
must not be red. A red chip suppresses the tick regardless.

- **#107 / #110 / #115 / #80** have a catalogue course, so their institution was checked against the
  27 IPG campuses and matched **all along**. What killed the tick was the *programme* comparison: the
  letter names the umbrella ("Program Ijazah Sarjana Muda Perguruan (PISMP)"), the record names the
  option each was given ("Sejarah Pendidikan Rendah (SK)"). No shared distinctive token → `clash` →
  chip red → tick suppressed.
- **#127** never answered the aliran query, so no catalogue course could be pinned. With no course
  there was nothing to check against, and the code fell back to comparing her recorded institution
  with the letter's — which is the same string, copied verbatim, address and all. It matched itself.
  Her chip was never red, because with no usable declaration there was nothing to disagree with.
  **Both conditions passed and neither meant anything.**

## The fix

`programme_agreement` is the twin of `institution_agreement`, same three rules: resolve the letter
through the catalogue; a *different* course is a clash; an *unresolvable* one is `unknown`, never a
clash. And for a tertiary record with no course, an institution that came **from** the letter can no
longer be used to verify that letter.

`offer_is_resolvable` had already documented the PISMP ambiguity as by-design — the letter names the
campus but not the aliran. The information that this comparison was unfair was sitting in the
codebase; nothing had connected it to the chip.

## What went wrong

**I deployed a guard that changed 72 records when the request was about 4.**

*Symptom:* the first live audit showed every matric and STPM row losing its institution status, and
several green Pathway chips going grey.

*Root cause:* the guard keyed on `chosen_programme.source` being offer-derived. That is **also** true
of every pre-U record — because request #7, shipped hours earlier the same day, had just made
`confirm_pathway` write them that way. The shape in my head ("an unlinked tertiary record") was
narrower than the predicate I wrote ("came from an offer"). Every test passed, because the tests
described the shape I meant.

*What prevents recurrence:* the guard is now tertiary-only with a test that fails if anyone widens
it, and the general rule is in `lessons.md`: **when a change alters a DERIVED value, the blast radius
is not the records you had in mind — it is every record whose fields satisfy your predicate.**

## What went well

- **The promise in the analysis is what caught it.** The estimate said "re-check every PISMP student
  against live data before and after". Running that *before* reporting anything is the only reason
  this is a paragraph in a retrospective rather than a second bug report.
- **`audit_pathway_ticks` computes both answers in ONE pass** rather than two runs a deploy apart.
  Same data, same instant — drift is removed as an explanation, and the "before" is reproduced by
  calling the old code path rather than by remembering what it did.
- **Both guards were bite-checked**, each failing exactly the tests that name it.
- **The requester's detail did the hard part.** Naming #80/#107/#110/#115 *alongside* #127 is what
  made the inversion visible; "the tick is wrong on #127" alone would have sent us the wrong way.

## Numbers

Live audit, old derivation beside new, across 143 applications: **22 changed, 82 unchanged, 39
without an offer letter.** 10 gained an earned tick (including #48, of the July regression); 7 lost
a self-awarded one; 5 had a red chip replaced by "cannot tell"; **no pre-U record changed.**

## Left open, deliberately

The **Reporting Date tick has no cross-check** — it appears whenever the letter carries a date,
because the shown value *is* the letter's date. That is why it survived on #127 when everything else
went. Raised with the owner rather than decided; recorded as **TD-211**.
