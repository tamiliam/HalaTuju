# Retrospective — the catalogue governs documents (config roadmap, Sprint 3a)

**Date:** 2026-07-29
**Deliverable:** the backend submission gates, blockers, income switch and verdict facts read the Layer 0
catalogue instead of hard-coded literals — with BrightPath's behaviour unchanged.
**Verification:** 5022 pytest passing · **no existing test edited** · production catalogue seeded and
verified against the code's own literals.

---

## The near-miss, which is the only thing about this sprint worth remembering

Every gate was wired. The full suite ran. **5018 tests passed on the first attempt.**

They passed because no fixture seeds the catalogue. Every test took the *no-programme* fallback branch;
none took the branch I had just written. Production, meanwhile:

| | |
|---|---|
| Applications carrying a programme | **143 of 143** |
| Rows in the catalogue tables | **0** |

So `resolve()` saw a programme, trusted the catalogue, and returned `{}`. Then
`documents_done = required_types.issubset(present)` — an empty set is a subset of anything — became
**vacuously true**, and `consent_blockers` raised none, and `income_doc_blockers` returned early.

**All 60 students inside the submission gate could have submitted with no documents at all**, and the
suite would have stayed green through the whole incident.

### What actually caught it

Not a test. A question: *the tests pass — but which branch do they take?* Then one query asking what
production's shape really is. The number that mattered (143 with a programme, 0 catalogue rows) took
about ten seconds to get and made the bug obvious.

### What was done about it

1. **The guard:** an empty catalogue means "not configured", never "requires nothing" — fall back to
   platform defaults, per kind.
2. **Four tests written from PRODUCTION'S SHAPE** — programme set, catalogue empty — rather than from
   what the code was meant to do.
3. **The guard was then disabled and the tests watched to fail.** A guard I have not seen fail is a
   guard I have not verified. Three of the four failed; the fourth (the converse case) correctly did not.

## The deferral that expired

Sprint 2 deliberately left production unseeded, reasoning that nothing read the tables so empty was as
inert as seeded. That was **correct when written and false the moment these gates shipped** — and
nothing in the process re-opened it. Production is now seeded (8 documents, 10 questions), verified
against the literals the code still gates on.

**When a sprint starts consuming what a previous sprint deferred, the deferral is part of this change's
blast radius.**

## What shipped

- `application_completeness`, `consent_blockers`, `_offer_blocks` and `income_doc_blockers` now ask
  `requirements.py`. Defaults reproduce today's behaviour by construction, so nothing moves.
- **The income route engine is touched in exactly one place: whether it runs.** `income_proof` is one
  switch over the whole of `income_doc_blockers`. Letting an organisation switch off "the father's IC"
  while leaving "his payslip" on would produce an assessment nobody designed.
- **A verdict fact whose evidence is not asked for is OMITTED** — not green (which claims we verified
  something) and not red (which claims a gap that is not one).
- `resolve()` is one query, memoised per application instance — `application_completeness` runs per row
  in list endpoints, so the naive version was an N+1 on a 143-row list.

## Two things that cost nothing because of earlier work

**Resolution tickets needed no change.** `_ticketable_unresolved` iterates `build_verdict`, so filtering
the facts filtered the ticket queue for free. Doing the verdict properly paid for the resolution layer.

**The per-student offer logic was never at risk.** "Core" means the *organisation* cannot remove the
offer letter; the STPM exemption and the genuineness gate are per-STUDENT rules and sit untouched. Two
different questions, kept separate.

## Deliberately not done

**`check2_queries.py`** — almost entirely income-engine driven, but it also carries academic and family
follow-ups, so gating it wholesale on the income switch would suppress those wrongly. It is a reviewer
follow-up queue, blocks no student, and cannot misfire until Sprint 5 allows a setting to differ. It
gets its own pass.

**The submit-time snapshot** — moved out of this sprint and flagged to the owner rather than dropped
quietly. It protects submitted students from a later configuration change, and no configuration can
change until Sprint 5; building the guard alongside the capability keeps them from drifting.

## Carry

- Sprint 3b: the front end reads the resolved set from the payload, and `COMPULSORY_DOC_TYPES` is
  deleted. It currently says `['ic','results_slip']` while the backend gates on more — **the two
  already disagree**, and 3b collapses them into one source.
- `check2_queries.py`, and the submit snapshot, both before Sprint 5.
