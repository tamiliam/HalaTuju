# Retrospective — Nav/IA N4: the sidebar becomes a rail

**Date:** 2026-07-28 · **Roadmap:** `docs/plans/2026-07-27-nav-ia-roadmap.md`
**Design of record:** <https://claude.ai/code/artifact/df8ab5ae-cc10-47b5-acc4-ed57e944a280>
**Migration:** none. **Backend:** none. **New dependency:** none.

---

## What Was Built

The scope sidebar now rests at 48px of icons and opens to 216px on hover or keyboard focus, over
the page rather than pushing it. The active row is the only brand-coloured thing in it. Pointing at
a row shows "Go to <page>" with a keyboard chord, and `G` then that letter jumps there.

- **The overlay is the load-bearing decision.** A spacer holds the collapsed width and the rail is
  absolutely positioned above it, so opening changes no layout. A rail that widened *in flow* would
  shift the page sideways underneath a cursor already travelling toward something.
- **Chords are optional on the registry and guarded by a test**, not by the type — the inverse of
  the usual "make a new dimension required" rule, and deliberately so: most routes will never earn
  a letter, and a required field would have forced a fake onto every one of them. The guard that
  matters is *uniqueness*, which a type cannot express.
- **`chordTarget` resolves against the VISIBLE menu**, so a chord never carries anyone to a page
  their sidebar does not offer. Courtesy, not access control — the page guard and the endpoint are
  untouched, as the registry's docstring has said since N1.
- **Per-group collapse was removed.** It shortened a long wide sidebar; the rail is short by
  construction.

**Numbers:** jest **968** / 63 suites (+35) · i18n **4090 × 3** · `next build` compiled, 66 pages ·
**24 files** (21 changed, 3 new).

---

## What Went Well

- **The preview replaced the spec, and it was better than one.** The owner approved an interactive
  mock-up rather than a written plan, which meant the open/close behaviour, the dot-versus-number
  badge and the collapsed group boundary were all settled by looking rather than by describing. The
  standing lesson ("build the preview at the first blocker") was written for reviews; this sprint
  shows it works as the *starting* artefact too, on a box where local sign-in is broken.
- **The Manual pass found a sentence that had been false for two sprints.** *"The links along the
  top are your workspace"* — untrue since N2 moved them to a sidebar, and missed by both previous
  currency passes because it contained neither word being grepped for. Grepping for what the copy
  MEANS, which was N3b's own lesson, is what caught it.
- **A second stale FAQ answer surfaced the same way** and was self-contradicting: *"It's in the
  sidebar … Payments card. There is no separate menu entry for it."* Both halves were true at
  different points in the last fortnight; neither was true together.
- **Debt was logged at introduction with its trigger named** (TD-187), which is the habit that made
  TD-181 close itself on schedule one sprint after N1 created it.

---

## What Went Wrong

**1. I answered five of the owner's questions for them and called them "settled".**
*Symptom:* "looks good, proceed" arrived with five open questions from the preview unanswered. I
recorded all five as decided, in a table, in the roadmap — including two about theming.
*Root cause:* the questions were mine to *ask*, so I treated silence as delegation. Two of them
(how many themes; whether a theme follows the person, the device or the tenant) were not
implementation details at all; they were product scope, and the owner said so as soon as they saw
what I had done: *"Themes should be its own planning."*
*System change:* the roadmap table now marks each answer with **who** settled it, and the two theme
rows are struck through as WITHDRAWN rather than deleted, so the record shows the correction rather
than hiding it. The narrower habit: when a question is about *what we are building* rather than
*how*, an unanswered question is not a defaulted one — do the part that does not depend on it and
leave the question standing.

**2. A reserved key smuggled a decision into code.**
*Symptom:* `uiPrefs.ts` shipped with `PREF_KEYS.theme` and a docstring saying the theme comes next.
*Root cause:* it looked like tidiness — one place for preference keys — but it silently asserted
that a theme is a *device* preference, which is exactly the question the owner had not answered. A
later sprint would have found the key already there and read it as settled.
*System change:* deleted, and the module now carries a note that its reasoning covers a menu's
width and does not generalise. General form: **a placeholder for future work encodes an assumption
about that work.** If the assumption is not yours to make, do not leave the placeholder.

**3. Two scoping mistakes on the test file, both from assuming a query was unique.**
*Symptom:* `getByText(/goTo/)` matched every row's chip; a dot assertion matched the icon.
*Root cause:* writing assertions against the whole nav when the thing under test belongs to one
row. Trivial, and it cost two runs.
*System change:* the chip and badge assertions now scope through `closest('a')`, and the dot has a
`data-badge` hook rather than being matched by a utility class — a class is a styling decision and
should not be a test's selector.

---

## Design Decisions

Logged in `docs/decisions.md` (2026-07-28):

1. **The rail overlays; a spacer holds its width.** The alternative — widening in flow — moves the
   page under a moving cursor.
2. **Chords are optional data guarded by a uniqueness test**, not a required field.
3. **A chord resolves against the VISIBLE menu**, so it cannot land on a page the sidebar does not
   offer — courtesy, not a fence, and the docstring says which.
4. **The pin lives beside the breadcrumb**, not in the account menu: it changes the thing
   immediately to its left, and a buried layout control is one nobody discovers.
5. **Per-group collapse removed.**

---

## Numbers

| | Before | After |
|---|---|---|
| jest | 933 | **968** |
| suites | 62 | **63** |
| i18n keys × 3 | 4086 | **4090** |
| Sidebar width at rest | 240px | **48px** |
| Routes with a keyboard chord | 0 | **14** |
| Manual sentences that were false | 2 | **0** |

---

## Carried Forward

- **▶ PF-1 is next, by the owner's own sequencing** — themes come after it, and cover admin,
  sponsor and student surfaces. `services.resolve_open_cohort()` still picks the open cohort
  platform-wide with no organisation context.
- **▶ Themes are their own planning exercise** (`implementation-planning.md`), not an N5. The
  measured groundwork stands as input: 1,537 hard-coded colours across 119 files, and a brand ramp
  that is already CSS variables and must not be touched by a theme.
- **▶ N3a still owed** — scopes endpoint + switchers, with its mandatory `FENCED_OR_EXEMPT` entry.
- **▶ TD-182** unfixed; **TD-187** (rail cannot scroll) and **TD-188** (three shell sprints with no
  browser pass) logged this sprint.
- **Owner tasks:** re-capture the Manual screenshots — now wrong twice over, and the manifest says
  to take them with the rail **pinned open**; review the ms/ta drafts for the four new strings.
