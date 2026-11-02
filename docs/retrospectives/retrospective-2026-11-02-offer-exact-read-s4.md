# Retrospective — Offer letters read exactly, Sprint 4: the new reader (2026-11-02)

Roadmap: `docs/plans/2026-11-01-offer-letter-exact-read-roadmap.md`. LIVE: main cfd02d91, api halatuju-api-01237-gdp,
no migration. Reader `OFFER_READER_VERSION` 2.4.0. Paid Gemini runs across S4 about RM19 (2.0.0 RM5.23, 2.2.0 RM6.22,
2.3.0 RM6.40, pilots), each on the owner's yes. Money behaves exactly as main (owner "1").

## What Was Built

- `offer_reader.py`: page 1 alone at high detail for identity fields; pages 2-3 at low detail fill blanks only. New
  fields `campus`, `reporting_venue`, `programme_code`. The PDF text layer is fenced as data, marker runs neutralised.
- `offer_ic.py` IC guard: a labelled IC is kept when it is the student's own (±1 digit) or a well-formed IC; a
  reference-line, unlabelled or source-less IC is corroborate-only (exactly the profile IC, else blank — it can give
  `match`, never `mismatch`); the text-layer backstop fills only a read that gave no usable number.
- Eval: `offer_s4_dry_run.py` (production, one read-only transaction, rolled back) replays the IC guard against the
  production profile IC from each cache's raw model read; a money-reach check (old code vs S4 code on all
  applications).

**Scores (fully exact on core fields), stored -> 2.3.0 caches:** held-out 19 -> 63 / 90, dev 31 -> 89 / 126. Production
dry run: 0 `-> mismatch`; the 16 IC losses of 2.2.0 recovered; realign 9 / link 4 proposals cleared by the matcher
session; money reach 0 changed.

## What Went Well

- The production dry run caught what the corpus could not: the cached IC blanks came from a guard that ran with no
  profile IC, so the eval-time "loss" was not the production result. Replaying the guard from the raw read settled it.
- The matcher session reviewed every realign / link proposal against the live catalogue and found a real matcher
  bug (app 337, a subset match through a printed typo), fixed and live before S4.
- Two adversarial reviews found real defects each time (multi-page low resolution, a false-mismatch path for a
  source-less IC, a forged text layer turning a wrong-person letter into `match`, and a money leak).

## What Went Wrong

1. **A money rule rode inside a reader sprint.** Why: the first review flagged that a not-offer letter could date the
   course, and the fix was added in place. Each fix then exposed a deeper money path (the synced reporting date,
   then `course_start_unknown` with no caller, QC and payments reading the date directly). Fix: the owner took it
   out; money is its own sprint (TD-465). Rule: a money behaviour change found inside another sprint is LOGGED and
   SPLIT, never fixed in place.
2. **The IC "loss" was reported as probably harmless before it was measured.** Why: the eval cache kept only the
   post-guard field. Fix: caches now keep the raw model read; the dry run replays the guard with the production IC.
3. **The money reach was first counted on a narrower question.** The first count missed 14 applications reached
   through the synced date; the reviewer found the route. Measure every path into the value, not the one changed.

## Carried Forward

- S5 known-format exact reader; S6 genuineness (app 329 doc 3494, IKM offer scored against the polytechnic
  fingerprint) plus the owner's chip-colour ruling (green fine, yellow look, red wrong; Pathway never red); S7 live
  re-read of changed letters (watch app 52, a portal photo whose inferred intake goes blank); S8 keep-exact gate.
- Money sprint: TD-465 and the owner's 2026-11-02 rulings in `docs/decisions.md`.
- Small field drops of 2.3.0 against 2.2.0 (issuer, campus) read as run-to-run variance; re-measure in S5.
