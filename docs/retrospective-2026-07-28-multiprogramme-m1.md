# Retrospective — M1: "which application is this about" stops being answered by position

**Date:** 2026-07-28 · **Roadmap:** `docs/plans/2026-07-28-multi-programme-applications-roadmap.md`
**Migration:** none. **New dependency:** none. **Approved scope:** M1 only.

---

## What Was Built

The third and last member of a family PF-1 opened. Something is resolved by taking the first row of
a set that was assumed to have one member:

| # | Where | Fixed |
|---|---|---|
| 1 | `services.resolve_open_cohort()` — which programme an application is FOR | PF-1, earlier today |
| 2 | `views._current_application()` — which application a REQUEST is about, **13 call sites** | **this sprint** |
| 3 | `application/page.tsx` — `applications[0]` | **this sprint** |

`_current_application()` carried *"latest wins"* in its docstring as though it were a rule. It was
an assumption that held only because one cohort had ever existed. A student holding applications to
two programmes uploads their IC for programme B and it attaches to whichever they submitted most
recently — silently, into the wrong organisation's hands.

**Numbers:** `pytest` **4957** (full scope) · `jest` **1039** / 67 suites · i18n **4151 × 3** ·
build compiled · **7 files**, no migration.

---

## What Went Well

- **The roadmap earned its keep before a line was written.** Decomposing first is what surfaced
  that the picker the owner asked for would have *created* the bug — it invites students into the
  one thing the system mishandles. Building the requested thing first would have been worse than
  useless.
- **Scenario 3 arrived mid-sprint and cost nothing**, because it landed on unapproved sprints. It
  retired a reading of scenario 1 (the tunnel is per-visit, not an account flag) and collapsed M4's
  picker and switcher into one application-aware list. Recording it took minutes; discovering it
  after building both would have cost a sprint.
- **The exception choice is the sprint's one real design decision, and it went against house
  style deliberately** — thirteen `try/except`s where forgetting one gives a 500, versus one class
  that makes the fourteenth call site safe without its author knowing. Written down in
  `decisions.md` because a future reader will otherwise "fix" the inconsistency.
- **Inertness is provable, not asserted.** The `(cohort, profile)` constraint excludes only
  `expired`, so one cohort means at most one live application. The tests must *create* a second
  programme to reach the bug.

---

## What Went Wrong

**1. I hardcoded a support address into new copy and the brand guard caught it.**
*Symptom:* `brand-guard.test.ts` failed on all three locales — `help@halatuju.xyz` in a message
value.
*Root cause:* I wrote the copy from scratch instead of looking at how neighbouring strings say the
same thing. `{supportEmail}` is one of five branding tokens `t()` already auto-injects, and an
adjacent message uses it for exactly this purpose.
*System change:* recorded as a lesson with the general form — on a mature codebase, a guard blocking
you usually exists *because* the sanctioned mechanism exists. Look for the mechanism before
reaching for the allowlist. Thirty seconds of grep.

**2. I nearly reported a failing suite as a real failure.**
*Symptom:* `AwardComprehensionQuiz.test.tsx` — "Test suite failed to run" — in a 67-suite run, on a
sprint that had touched neither that component nor anything it imports.
*Root cause:* worker exhaustion on the 8 GB box, already documented for `next build` and not for
jest.
*System change:* it passed in isolation, but isolation is a hint rather than proof — it changes the
worker count, so it cannot distinguish "flaky under load" from "broken by an interaction". A full
green re-run is the only thing that rules the second out, and it costs twenty seconds. Now a lesson.

**3. A compound command silently did nothing because the shell had reset its directory.**
*Symptom:* `cd ../halatuju-web && cat >> …` — the `cd` failed, `&&` short-circuited, and the heredoc
never ran. Two dependent commands then failed confusingly.
*Root cause:* assuming shell cwd persisted from an earlier call. It had reset to the workspace root.
*Consequence:* none, because the `&&` meant nothing was half-written — which is the argument for
`&&` over `;` in these chains. Absolute paths from then on.

---

## Design Decisions

Logged in `docs/decisions.md` (2026-07-28):

1. **The guard is an exception, not a return value** — so a fourteenth call site cannot reintroduce
   the bug, at the cost of diverging from the module's explicit-`Response` style.
2. **The application screen shows nothing rather than one of several** — "latest wins with a note"
   is still the screen choosing for the student.

---

## Numbers

| | Before | After |
|---|---|---|
| Positional "assume one" resolutions in this family | 3 | **0** |
| Call sites that can misattribute a request | 13 | **0** |
| pytest | 4947 | **4957** |
| jest | 1029 | **1039** |
| Migrations | — | **0** |

---

## Carried Forward

- **▶ M2–M4 are NOT approved.** Until M2 gives the client a way to NAME an application, two live
  applications means a refusal. That is the correct floor — a locked upload is recoverable, a
  document filed under another foundation is not.
- **▶ Re-plan M2–M4 when a second programme is actually close.** The scenarios will have moved; they
  already did once, mid-sprint.
- **▶ TD-189** (no picker on a bare `/apply`) is unchanged and still triggered by a second open
  programme.
- **▶ Still not engineering, still blocking a second tenant:** Sprint E (erasure) and the unsignable
  DPA.
- **TD-182** unfixed; **TD-188** — five consecutive sprints have now closed without a browser pass.
