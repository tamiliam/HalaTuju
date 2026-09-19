# Retrospective — Code health H8: the income rule has eleven homes, and the sprint stopped at its own gate

**Date:** 2026-09-19 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H8 of H19
**Built by:** an Opus 5 agent to a written brief with a hard stop gate; the lead verified the two
most visible findings in the source, re-ran the suites, recorded the findings, and closed.
**Outcome: PHASE A DELIVERED, PHASE B STOPPED — by design. No production code changed.**
**Freeze status:** in force. The arm of the arc that touches eligibility now waits for the owner.

## What Was Built

- **A verified map.** TD-235 said the income rule has four homes. It has **eleven** — six in the
  api, five in the web — each answering a slightly different question (*may she submit · does a
  submitted student still read complete · what shall we draw · what shall we ask for · what does
  the officer chase · what does the verdict say · which copy is live*).
- **Two characterisation suites, green on the untouched tree:**
  `apps/scholarship/tests/test_income_evidence_homes.py` (37 tests, H5 factory, product-reachable
  households) and `src/lib/__tests__/incomeEvidenceHomes.test.ts` (18 tests, the same scenario
  table plus cross-language comparisons, each quoting the api test that pins the other side).
- **Sixteen pinned disagreements** — places where two homes give different answers about the same
  household *today*. Recorded in full as **TD-262**.

## What Went Well

- **The stop gate worked, and it was the brief's most important line.** *"No student's answer may
  change, and that must be proven before any code moves."* Not one home passed. The agent moved
  no code, and delivered the map instead of a merge with an asterisk.
- **It settled the frozen-gate question from the documents instead of escalating it.** The
  roadmap's H8 goal — "the frozen gate reads the single answer" — would have **un-submitted real
  students**: the legacy document-type arm is *more permissive* than the live rule in four cases,
  and a failed completeness check also nulls the student's `requirements_snapshot`. The inline
  comment, the 2026-06-05 gate decision and TD-235 incident 1 all say the same thing: the OR exists
  so the frozen copy can only ever **widen**. It is load-bearing in both directions.
- **Bite 2 is the proof TD-235 never had.** Breaking the *served* api answer turned the api table
  red and left the web table **green**. If the web read the served answer it would have moved. It
  did not. "The rule has more than one home and only one is ever updated" — demonstrated.
- **It measured the guard before proposing it.** The fifth-home guard would flag 73 sites — but
  `'str'` is both a document type and an income *route*; 15 of 29 `== 'str'` comparisons are the
  route. A naive guard would cry wolf on half its hits. That is a finding about the ticket.

## What Went Wrong

**1. The lead planned a unification sprint on a rule nobody had characterised.**
- *Symptom.* The roadmap sized H8 at ~9h to "make four homes read one answer". Phase A alone took
  the whole sprint and showed the goal, as written, cannot be done safely.
- *Root cause.* The plan was built from TD-235's prose (three incidents, four homes), not from the
  code. H7's lesson — characterise every copy side by side *before* designing the move — was
  written the same day and not yet applied to the plan that followed it.
- *System change.* The roadmap's H8 is rewritten: Phase A is the deliverable; Phase B is split
  into owner-ruled pieces (TD-262). H9–H10 (de-mirror) inherit the rule: **characterise first, and
  a mirror is only deleted where the two sides already agree.**

**2. Real students are living with these disagreements now** — none created by this work, all
invisible before it. The two on a student's own screen, verified by the lead in the source:
`ScholarshipReview.tsx`'s category map has no `income_support_doc`, so the one letter that proves a
family's income is filed under **"Other"** on her consent read-back; and the Documents tab's green
cue has no STR arm (its comment explains the assumption that fails), so a salary-route student with
a genuine STR is accepted by the server while her own screen still asks for a payslip.

## Numbers

| | Before | After |
|---|---|---|
| pytest `-n auto` | 6,917 | **6,954 passed · 3 skipped · 0 failed** |
| jest | 2,565 / 140 | **2,583 / 141** |
| Production code changed | | **none** — two test files added |
| Homes of the income rule, known | 4 | **11** |
| Disagreements pinned | 0 | **16** |
| Mirrors retired | | 0 of 58 — none could be retired safely |
| Every code-health reading | | delta 0 · `std` ok |
