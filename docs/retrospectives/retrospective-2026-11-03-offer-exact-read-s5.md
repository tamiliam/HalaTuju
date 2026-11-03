# Retrospective — Offer letters read exactly, Sprint 5: the Exact read covers more letters (2026-11-03)

Roadmap: `docs/plans/2026-11-01-offer-letter-exact-read-roadmap.md` (S5, "Plan (2026-11-03)"). LIVE: main ae443f45,
api halatuju-api-01240-cg2, no migration, owner go 2026-11-03 after the production dry run. `offer_parse.PARSER_VERSION`
2.0.0. No paid call in the whole sprint (cached text only; S2's Vision capture).

## What Was Built

- **Answers for the 71 stored Exact reads** (dev), checked by the owner on `review_s5_exact.html`: every field right.
  One owner ruling from it: the reporting date is the DATE ONLY (decisions.md 2026-11-03); 20 answer files cut.
- **`offer_parse.py` 2.0.0** — one shared block reader that takes each label's value by its SHAPE, in letter order
  (the 2026-09-10 decision's "per-label recovery written once"); the exit guards kept. It closed the five failure
  classes (A STPM six labels, B the matric glued text layer, C names with no parentage marker, D the polytechnic
  session numeral, E block and label variants) and the two wrong values (the poly offer date was the registration
  date; a matric range took its last day). Conventions: poly code -> `programme_code`, intakes keep their words,
  `candidate_nric_source`, the house date shape. The family readers moved verbatim to `offer_parse_families.py`.
- **`offer_exact.py`** — the ONE entry point: page-1 identity from the same source as the body, the IC guard on the
  Exact path (a blanked IC means no lock), the merge (the parser's keys whole, the dates merge-preserve).
  `vision.py` net -14 lines.
- **Eval:** `offer_parse_check.py` (EXACT / WRONG / CONTROL-LOCKED per letter, the pipeline score),
  `offer_s5_caches.py` and the S5 mode of `offer_s4_dry_run.py` (re-derives each lock against the live row with the
  production profile IC; counts the money reach and any new wrong-person red).

**Numbers.** Corpus locks 51 -> 96 of 287. Dev 86 EXACT, held-out 10 EXACT, 0 WRONG and 0 control locks on both.
Pipeline fully exact (lock over the 2.3.0 AI read): dev 89 -> 92 / 126, held-out 63 -> 66 / 90, no core field down.
The 21 at-risk stored Exact reads: 21 / 21 re-lock exact (70 of the 71 re-lock; `a30` was a wrong 1.3.0 lock on a
noisy layer). Dev real known-format letters 16 / 17. Scholarship suite at ae443f45: 9,997 passed, 3 skipped.
**Production dry run:** 96 locks, 87 live; `new_red` 0; `money:intake_year` 0; `ic_refused_live` 0;
`money:reporting_date` 6 (apps 114, 29 — Tarikh Kemasukan, not the online-registration end; 58, 71 — a range's first
day; 319, 419 — blank -> filled), all matching the owner's answers; realign 3 -> `same_course`, fill 1, Name
mismatch -> partial 1 (app 177), pathway ticks -> match 7. Cockpit reviewed: no objection, one finding (TD-473).

## What Went Well

- **The corpus check gated the build.** `offer_parse_check.py` was written first; every rule was tuned against it,
  and it found WRONG reads in the LOCKS that production already held (a matric stream "Yuran Pendaftaran:" on `a30`)
  — the owner-checked answers for the 71 made "0 WRONG on dev" measurable where it had not been.
- **Shape over position.** One reader replaced the positional zip that had broken twice (#125, #142). The #142
  letter now leaves the Jurusan empty instead of shipping a date in it.
- **The dry-run tie-out.** All six reporting-date changes on live records matched the owner's answers one for one;
  the intake year moved on no document; no new wrong-person red.
- **Masked inspection.** Layouts were studied with rare tokens and digits masked; no student value left the corpus.

## What Went Wrong

1. **The held-out set was run three times, not once.** Run 1 found one WRONG (a polytechnic code whose dash the OCR
   dropped); the fix was a general rule with a twin, and held-out was run again (run 2) and once more after the
   first review (run 3). That one letter has been seen while tuning, so the held-out evidence is weaker than "run
   once" claims. Why: the WRONG was a real general class and shipping it was worse. Rule: when held-out finds a
   WRONG, fix by class, say so in the report, and count the runs — never present a re-run as the first.
2. **Two adversarial review rounds found 2 High and 2 Medium after the builder's own checks passed.** H1: the
   identity could be read from a hidden PDF layer beside a Vision body (another person's IC locked as `match`). H2:
   a scanned page 1 fell back to later pages. Medium: a cubic ReDoS (41 s on 2,000 spaces), portal pages quoting the
   title, matric names taken from place / stamp / letter words and wrapped tails, a quadratic block scan. Why: the
   builder tested what the corpus holds; the reviewer tested what an attacker or an odd file holds. Rule: an
   identity path is reviewed adversarially before the push (memory: feedback_adversarial_review_before_ship), and
   every new regex with two whitespace runs gets a timing test.
3. **A tell measured on the corpus was too broad at first.** "SEMAKAN" alone made a real polytechnic letter fall
   back; only the dev re-run showed it. Rule: a new refusal rule is re-measured on dev before it is reported.
4. **`identity_disagree` rarely fires** (a digital PDF's page 1 starts its whole layer); it guards the odd file and
   is not a measured fix — said so in the CHANGELOG.

## Design Decisions

- The Exact read owns its keys whole (a stale AI campus / code / address cannot survive under an "Exact" chip); the
  dates keep merge-preserve, and a parser date that does not parse never replaces one that does.
- Every doubt about a name or an IC reads "no lock" (-> the AI reader): a wrong name is a false wrong-person red, a
  fall-back only costs one Gemini call (~US$0.0064).
- No university or PISMP reader (the data gate: 2.3.0 is already fully exact on UMS / UM dev).

## Carried Forward

- **S6** — genuineness fixes and the owner's chip-colour audit (rulings 2026-11-01 / 2026-11-02; app 329 named).
- **S7** — the live re-read is now safe for the 21 at-risk reads. The S7 list = the 6 reporting-date letters + every
  live letter whose Exact read changed (the dry run's 87 live locks), on the owner's yes to the list and the cost.
- **S8** — keep it exact (the scorer and `offer_parse_check.py` as a sprint-close gate).
- **TD-465** — the money sprint (a course-start year can set the award; QC / payments read `reporting_date`).
- **TD-473 (Cockpit)** — a pre-U letter ticking Pathway `match` against a degree pick by a shared word; the
  `pathway_engine.py` split first. **TD-474** — a one-word town line after an STPM school name (L3).
