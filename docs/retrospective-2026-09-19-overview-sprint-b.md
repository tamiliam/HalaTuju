# Retrospective — Overview phase 2, Sprint B: the arrows, and the drag that was not built

**Date:** 2026-09-19 · **Roadmap:** `docs/plans/2026-09-18-overview-phase-2-roadmap.md` · **Sprint:** B of 2 (the phase is now complete)
**Built by:** an Opus 5 agent to a written brief and the standing hard rules. The lead reads the
report and pushes.
**Outcome: an org admin can put the five Overview panels in any order, from the screen that was
already there.**
**No backend code changed, no migration, no deploy.** Four source files, four test/locale files.

## What Was Built

- **An Up and a Down arrow on every card of the Customise editor**
  (`src/components/admin/overview/CustomiseLayout.tsx`). Pressing one moves that panel one place;
  Save sends the whole list, in its new order, to the endpoint Sprint A already built. Nothing on
  the server moved: `sections` was always an ordered list, always validated as a permutation of the
  five customisable widgets, and `saveOverviewLayout` already PUT the lot. `admin-api.ts` was not
  touched — it is on the Phase-4 oversize list (H13), and the standing rule would have forced that
  split sprint first.
- **The arithmetic is `overviewLayout.moveItem`'s, not the component's.** The pure helper and its
  end cases shipped with Sprint A, untouched; the component holds the gesture and nothing else. A
  second spelling of "swap two rows" inside the editor is the copy that would have silently won.
- **The accessibility decisions, each one taken rather than inherited:**

  | decision | why |
  |---|---|
  | real `<button>`, never a div | the keyboard has to reach it at all |
  | named for the panel AND the direction ("Move Money up") | ten controls all called "Move up" is what somebody reading the page through its list of buttons would otherwise be handed |
  | the first row's Up and the last row's Down **disabled** | `moveItem` already refuses those moves harmlessly; disabling them stops inviting a press that does nothing |
  | 44px square | an arrow is the smallest control on this screen and the likeliest to be used with a thumb |
  | **the moved row keeps the keyboard** | pressing Up three times must move one panel three places; focus dropped after the first press leaves the person at the top of the page not knowing which row they were on |
  | **no live region** | the codebase has no polite-live-region pattern (see What Went Wrong 2) |

- **Three locale keys × three languages** — `customise.orderHint`, `customise.moveUp`,
  `customise.moveDown` — and the whole `customise` block added to the i18n guard's dynamic families.
- **Eight tests.** Three mount the **real Programme Overview page** and drive it from the Customise
  button (the drawn order changes; the disabled end moves with the row; the save carries the new
  order; every arrow's accessible name). Five sit on the editor (44px, the move, focus kept, focus
  handed to the other arrow at an end, Save woken by a reorder with no switch touched).
- **Drag-and-drop was NOT built** — the roadmap's own words asked for it. See below.

## What Went Well

- **The pure helper made the sprint small.** `moveItem` existed, with its end cases tested, because
  Sprint A wrote it in advance. The whole feature is one handler, two buttons and a focus rule; the
  arithmetic was never in question, so the tests could be about the SCREEN.
- **The module's own docblock decided the biggest question.** `overviewLayout.ts` had recorded,
  since Sprint A, that "a `drop` event jsdom never really fired" proves nothing — one paragraph
  above the helper a drag would have used. The argument against drag-and-drop was already written
  down by the person who would have built it. A comment doing real work a day later.
- **Five bite-checks, five bit — including the one nobody asks for.** Reorder ignored → 4 tests red;
  ends un-disabled → 2 red; save sending the ORIGINAL order → 2 red; the focus rule's end-flip
  removed → 1 red; and a cosmetic `gap-1` → `gap-2` stayed green, so the suite is not crying wolf.
  Each injected needle was proved unique first, each restore verified by SHA-256.
- **No budget moved and no reading got worse.** `code_health` is identical to the last run on every
  column (fix% 42, big 25, long 15, dup 4, mirror 3, guard% 19, `std` ok, 0 FAIL); no suppression,
  no skipped test, no ledger gained a member.

## What Went Wrong

1. **The roadmap asked for a feature that its own source file had already argued against — and
   nothing connected the two.**
   - *What happened:* the sprint table said "up/down buttons **+ native HTML5 drag-and-drop**". The
     module those buttons live in says, in its first paragraph, that a jsdom drop proves nothing.
     Both were written on 2026-09-18, by the same arc, a few hours apart. The plan was never
     revised; a builder following it literally would have shipped an untestable gesture.
   - *Root cause:* a roadmap row is written at planning time and a docblock at build time, and
     nothing re-reads the first against the second. The plan named a TECHNIQUE ("native HTML5
     drag-and-drop") rather than the outcome ("an admin can reorder the panels"), so obeying it
     meant obeying the technique.
   - *System change:* the roadmap row now records what was built and what was not, with the reason,
     and `reorderByDrop` carries a comment at the site saying why it is kept unused —
     `docs/lessons.md` has the general form. **Sprint-start should read a sprint's row against the
     docblocks of the files it names**, which is one grep, not a review.

2. **The quality bar asked for a screen-reader announcement, and there was no pattern to follow.**
   - *What happened:* "announce the new position to a screen reader (a polite live region) **if the
     codebase already has a pattern for that**". It does not. The only `aria-live` in the tree is an
     assertive error alert on the apply page; `SaveBar` — the console's one status surface — has no
     `role="status"` at all.
   - *Root cause:* the platform has never needed one, so the first screen that does would become
     the author of a convention nobody reviewed. A five-row editor is a poor place to invent one.
   - *System change:* skipped, and **recorded in the roadmap and here rather than silently left
     out** — an omission nobody wrote down is indistinguishable from forgetting (the H10 lesson).
     Focus retention carries the news instead: the moved row keeps the keyboard, so the next thing
     read is that row. **If the console ever wants a polite status pattern, it is a platform
     decision with its own sprint, and `SaveBar` is where it belongs.**

3. **The end case that breaks by itself was nearly missed: a row arriving at an end disables the
   arrow that was just pressed.**
   - *What happened:* the first implementation relied on React keeping focus through a keyed
     reorder — which it does, and which is enough for a move in the middle of the list. Pressing Up
     on the second row moves it to the top, the Up arrow becomes `disabled`, and the browser blurs
     a disabled element to nothing: focus lands on `<body>`, at the top of the page.
   - *Root cause:* "focus is preserved across a reorder" is true and is not the whole claim. The
     property that matters is "focus is on a control that still exists and is still enabled", and
     the reorder is exactly the event that can change the second half.
   - *System change:* focus is handed to the arrow pointing back the way the row came, and the test
     `hands focus to the other arrow when the row lands at an end` pins it — bite-checked by
     removing the flip (1 test red). The general rule is in `docs/lessons.md`.

## Design Decisions

Recorded in `docs/decisions.md` (2026-09-19): arrows instead of drag-and-drop for the Overview
layout editor, with `reorderByDrop` kept unused.

## Numbers

- **8 files** (2 source, 3 test, 3 locale). No backend file, no migration, no deploy.
- **2,904 jest / 159 suites** (+8, baseline 2,896) · tsc **0** · lint **0 errors** (17 warnings,
  all pre-existing; none in a file this sprint touched) · `check-i18n` **PASS**, 5,388 keys ×3 ·
  `next build` **exit 0**.
- api untouched: `manage.py check` **0 issues**, `makemigrations --check --dry-run` **no changes**.
  pytest was not run — no api file was edited.
- `code_health` (read-only): **0 FAIL**, every reading identical to the previous run.
- **Bite-checks: 5 injected, 5 behaved** (4 red as expected, 1 green as expected). None silent.
- No time estimate was given, so there is no planned-versus-actual figure.
