# Retrospective — the front end reads the payload (config roadmap, Sprint 3b)

**Date:** 2026-07-29
**Deliverable:** the student Documents tab renders what the programme asks for, resolved server-side.
The duplicate rule in `halatuju-web/src/lib/scholarship.ts` is deleted.
**Verification:** 5077 pytest (scholarship + courses + reports) · 1137 jest / 76 suites · `tsc` clean
· `next build` clean · i18n 4293 ×3 · `makemigrations --check` clean · **no migration** · both states
reviewed in a browser before merge.

---

## What this sprint actually found

The roadmap said two descriptions of "which documents are compulsory" disagreed. Scoping found
**four**, disagreeing in three different ways:

| Where | Said the required documents were |
|---|---|
| `services.py` (the live gate, since 3a) | ic · results_slip · offer_letter · income route |
| `COMPULSORY_DOC_TYPES` | ic · results_slip |
| `documentsComplete()` | ic · results_slip · parent_ic · income |
| The JSX itself | four sections, `required: true` typed inline at each call site |

And the surprise: **the two constants were nearly dead.** They were consumed only to build the
`DocType` union; `documentsComplete()` had no caller outside its own test. What actually governed
what a student saw was the JSX — four hand-written sections, each naming a document and asserting
its own `required: true`.

So the deletion was the easy half. The sprint was rewiring the render.

## The bug that was live the whole time

`COMPULSORY_DOC_TYPES` marked two documents with a red asterisk while the submission gate enforced
four. A student could satisfy every card the page called compulsory and be refused at submit with
nothing on screen explaining it. This was not a regression anybody introduced — the offer letter was
promoted to compulsory for every route on 2026-06-05 and the front-end copy of the rule was not
touched, exactly the shape of `docs/lessons.md` (2026-07-26): *retiring a rule is not done when the
enforcing code changes, but when every mirror of it does.*

## A document that had gone missing from the record

The tab renders `card('school_leaving_cert')`. That code appears in **neither** the Layer 0 catalogue
**nor** the front end's own `OTHER_OPTIONAL_DOC_TYPES` — nor even in the `DocType` union, which
compiled only because the card helper takes a bare `string`.

It was harmless while nothing consulted those lists to decide what to DRAW. From this sprint the
catalogue does, so shipping without noticing would have **silently withdrawn a document students can
upload today**. It is now in the union, the platform fallback and the seeded catalogue.

This is 3a's rule 4 arriving from a new direction. That rule was written about deferrals; the general
form is broader: **when a sprint changes what a list is USED for, everything the list ever omitted
becomes this change's blast radius.** A list nobody reads is never wrong.

## What shipped

- **`requirements.payload_for()` → `requirements.documents.{required,optional}`** on the student
  application payload, beside the `completeness` block that already pays for the query.
- **`documentRequirement()` / `asksForDocument()`** are the only readers. Every section, the income
  aggregate and the Other bucket route through them.
- **A section whose only document is off collapses out entirely.** A heading over nothing reads as a
  page that failed to load. The Other bucket thins instead, and vanishes only when empty.
- **`income_proof` stays one switch over the whole route engine.** The utility bills clear two
  independent filters — the route engine's ("does this household's route surface a bill?") and the
  catalogue's ("does this organisation collect one at all?"). Neither can reach inside the other.
- **`DOC_TYPES` stays a static literal**, and that distinction is load-bearing: what a programme ASKS
  FOR is configuration; what a document type IS remains a closed set with recognition logic and a
  versioned genuineness model behind each entry. Keeping the vocabulary static is what makes this a
  catalogue rather than a form builder.

## The absent-block decision, and why it is the opposite of 3a's failure

A payload with no `requirements` block degrades to **`'optional'`** — every card renders, nothing is
asserted compulsory. Not to "off", which would blank the page; and not to a front-end copy of the
platform defaults, which would reintroduce the very mirror this sprint deleted.

The reasoning is that the front end **displays and has never been the gate**. Missing information
should cost the red asterisk, not the page. `application_completeness` on the server still decides
whether a submission is allowed, so the degraded state is honest rather than permissive.

## What went wrong, and what changed because of it

**A test passed for the wrong reason and I nearly kept it.** The first version of
`test_a_programme_promoting_a_bill_to_required_reaches_the_student` asserted the promoted bill was in
`required` and not in `optional`. Both hold if EVERY document is reported required — a real way to
get the payload wrong, and one that would render as a wall of red asterisks. Found by the bite-check,
not by review. Fixed by asserting the *neighbour* did not move.

*System change:* when a test asserts a value moved, assert something comparable did not. A test that
only checks the thing that changed cannot distinguish "this moved" from "everything moved."

**The seam module's own docstring was two sprints stale.** `requirements.py` still opened with
"⚠ THIS SPRINT IS DELIBERATELY INERT. Nothing calls these functions to make a decision yet" — false
since 3a wired the gates. A reader would have believed it. Corrected to a short status history.

*System change:* a docstring that describes the CURRENT sprint has a shelf life. Write status notes
as a dated sequence, not as a claim about now.

**`apply.docs.*` label keys do not exist in any message catalogue.** All nine catalogue rows point at
i18n keys with nothing behind them. Not consumed by anything (3b sends codes; the page keeps using
`scholarship.docs.type.<code>`), so not in this sprint's blast radius — but Sprint 5's admin screen is
the first thing that will render them, and it must create them rather than discover them missing.
Logged as **TD-197**.

## Guards verified by watching them fail

Both new mechanisms were disabled and the tests observed to fail before being restored — 3a's rule 3.

- `payload_for` made to report everything as required → **3 of 7** backend payload tests failed. The
  4 that survived were testing off-ness and sorting, which that break preserves.
- `documentRequirement` made never to return `'off'` → **7 tests failed** across the render suite and
  the lib suite, including every "this section disappears" case.

## The first render test this component has ever had

`ScholarshipDocuments.tsx` is ~1,900 lines with ~25 unexported in-file components and had **never
been mounted in a test**. The closest thing was `docFileLayout.test.ts`, covering one pure helper.
That absence is the mechanical reason a wrong list of compulsory documents could sit in the codebase:
nothing asserted what the page draws.

It now has seven tests, scoped narrowly to "does the tab render what the programme asks for" — the
sandbox's existing fixtures made it cheap, because a component that can be mounted against fixtures
in a browser can be mounted against them in jsdom. Upload, deletion and the income route logic keep
their own homes and are not re-tested here.

## Reviewed before it shipped

Both configurations were opened in a browser on the design sandbox — the full form and a lean
programme (identity + results only). This is the first sprint in months that could be *seen* before
merge; the sandbox needs no API and no login, so TD-194 does not block it.

The lean state confirmed the collapse behaviour: Pathway and Household income gone entirely, Other
holding its one survivor, no orphan heading, no console error.

## Production state at close

| | |
|---|---|
| Document items in the catalogue | **9** (8 + `school_leaving_cert`, seeded this sprint) |
| Per-programme overrides | **0** |
| Applications carrying a programme | **143 of 143** |
| Applications inside the submission gate | **41** |

With no overrides, every application resolves to the catalogue defaults, which reproduce the
hard-coded behaviour by construction. The one visible change for a BrightPath student is the offer
letter and the income section carrying the compulsory marker they always deserved.

## Carry

- **`check2_queries.py`** and the **submit-time snapshot**, both before Sprint 5 — unchanged from 3a.
- **TD-197** — the catalogue's `apply.docs.*` / `apply.questions.*` label keys have no messages
  behind them. Sprint 5 owns it.
- Sprint 4 adds `questions` to the `requirements` block. A test pins the current key set so that
  arrives deliberately.
