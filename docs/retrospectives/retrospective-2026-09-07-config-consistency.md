# Retrospective — the console's one save bar, and an intake round you can edit

**Date:** 2026-09-07
**Branch:** `feat/config-consistency` (worktree `.worktrees/config-consistency`, off `origin/main`
at `acac48e2`)
**Migration:** none. **Backend:** none. **Web only**, 14 files.

---

## Why it ran

The owner's second live review of Programme → Configuration, taken deliberately *before* the gift
switcher: *"Before we take on item 3, I want to look at the Configuration page… I want consistency
across the platform."* Four findings.

Three of them turned out to be one defect wearing four faces. The fourth reversed a ruling the
owner had made the previous day, and — after that ruling was put back to them — was un-reversed.

---

## What was actually wrong

I measured before agreeing to anything, and the measurement is the whole story:

| Tab | Save bar | Idle sentence |
|---|---|---|
| Organisation → Configuration | sticky bar, button right | "No unsaved changes" |
| Organisation → Colours | sticky bar, buttons right | "Nothing to save" |
| Programme → What we ask for | sticky bar, buttons right | "Nothing changed yet." |
| Programme → Rules | **no bar, button LEFT** | "Nothing to save — no changes have been made" |

And the rest of the console: **eleven** save controls carrying that same fact as a hover `title` on
a greyed button, and **zero** printing it as visible text. So the sentence the owner questioned was
not the house style being applied inconsistently — it was a one-off, and the Rules tab was the only
place it existed.

The intake-year tab had its own version of the same shape: the one-open-round caution rendered
**under** the table it governs, the only banner on the four screens that did.

**The lesson is the counting.** Had I reasoned from the neighbouring tab, I would have found two
variants and picked one. A convention with no single home is not a convention; it is the last
author's memory, and it drifts once per author. The fix had to be a component.

---

## What shipped

### `components/admin/SaveBar.tsx` — the one home

Sticky grey bar, status on the left, buttons on the right, `SAVE_BAR_PRIMARY` /
`SAVE_BAR_SECONDARY` for the button styling. **Idle renders nothing at all.** Adopted by all four
tabs, including Colours, whose four-verb toolbar keeps its own shape inside the shared shell.

**⚠ What the bar deliberately does NOT own: whether the button sleeps.** Each tab keeps its own
`dirty` computation and its own closed outcome union. The dangerous direction here is the opposite
of the reported bug — request #6 (2026-08-01) exists because a Save wrongly ASLEEP strands real
work — and one shared "is this dirty?" across four unrelated shapes of state is exactly how a tab
starts sleeping through an edit. The bar owns the layout and the silence.

Request #6's ruling is untouched: a Save with no edit behind it still sleeps, still tested per tab.
Only the repetition of that fact in prose is gone; the words moved to the button's `title`.

### The intake-year tab

- **The caution moved above the table.**
- **A round can be edited** — its name and its window. `AdminIntakeYearDetailView.patch` has
  accepted both since the gift-setup sprint and **no screen ever called it**, so this is web-only.
- **The year and the short code are NOT offered**, because the endpoint has never taken either: the
  code is the round's permanent identifier and the year is what the list sorts on. The dialog says
  so on screen rather than drawing a box the server would silently ignore — which is the exact
  defect this whole review round is about.
- **Clearing a date sends `null`, not `''`.** `_window_from` reads absent / empty / a date as three
  different instructions, and `null` is the one that WITHDRAWS a stated window. Without it a
  schedule could be changed but never taken back.
- **The dates speak** — `windowState` puts a plain-words line under the range. A round with no
  stated dates renders a bare dash and no line: that is the production shape (nothing was
  backfilled, the live 2026 intake included) and it must never read as an error.
- **The dates warn** — opening a round outside its own stated window asks first.

---

## The ruling that was reversed and then kept

The owner asked for the dates to control opening. That reverses their own ruling of 2026-09-06:
*the window describes; it opens nothing.*

I named the ruling, its recorded reason (a clock fires whether or not the gift's rules and
questions are finished — real students against a half-built form), and two facts a clock would trip
on **today**: every existing round carries NULL dates, and nothing runs on a schedule for this. The
owner chose option A and the ruling stands.

**The real complaint was underneath the ask.** Dates printed on a screen that decided nothing read
as furniture — the same defect that killed "Next: set the rules" the day before. That is fixable
without the clock, and option A is that fix.

**⚠ The warning asks; it does not refuse.** The server accepts an out-of-window open deliberately.
A confirmation nobody could get past would be a client-side gate the server does not hold — the
shape that makes a button lie. The load-bearing test is *"goes ahead and opens once the person
confirms"*: every obvious test asserts the dialog appears, and all of them would still pass if a
later edit quietly made the confirm a no-op.

---

## A rule that was NOT breached, and nearly self-inflicted

`windowState` derives in the browser. The reflex was to call that a breach of *serve, don't derive*
and push it server-side.

It is not. That rule bans a screen **predicting a server refusal** — because a client copy of a
server rule drifts and the button then lies about what the server will accept. Here the server
accepts an out-of-window open on purpose, so there is no verdict to contradict; this is arithmetic
on two dates the row already carries. **The test is whether a server verdict exists for the screen
to disagree with.** Getting it wrong in the cautious direction would have cost a round trip per
render and bought nothing.

---

## Bite-checks

Three, each injection verified as landed before the suite ran, each restored by writing the
original bytes back.

| Injection | Expected | Got |
|---|---|---|
| Delete the out-of-window confirm from `pressOpenToggle` | the two "asks first" tests fail | **3 failed** |
| Send `edit.opens_on` instead of `edit.opens_on \|\| null` | the withdraw test fails | **2 failed** |
| Move the caution banner back under the table | the ordering test fails | **1 failed** |

---

## Gates

`jest` **1810** (+16) · `tsc` **24** (the TD-221 baseline, all in old test files, none new) ·
`next lint` **0 errors** · `check-i18n` **4865 × 3** · `next build` **exit 0** · no backend files
touched, so `pytest` and `makemigrations --check` are unchanged.

**Every gate ran inside the worktree**, with `node_modules` junctioned to the main checkout's
install. That is the correction owed from the previous sprint, where the merge, the gates and a
`.next` force-delete all happened in the shared checkout while two other agents were working in it
— the most likely cause of three unexplained `next build` failures that day, and of any breakage
they saw.

---

## i18n

Five keys retired — the four idle sentences (`orgSettings.config.nothingToDo`,
`orgSettings.colours.nothingToDo`, `programme.config.unchanged`) plus two "unsaved" variants
collapsed onto one shared `common.unsavedChanges`. Thirteen added for the edit dialog, the window
states and the open confirmation. Parity **4865 × 3**; **ms and ta are my first drafts.**

---

## Owner post-check

As the BrightPath `org_admin` (`elanjelian@me.com`):

1. **Programme → Configuration → Intake year** — the amber caution is now **above** the table.
2. Each round has an **Edit** link: name and both dates, with the year and short code named as
   fixed. Clearing both dates and saving withdraws the window.
3. Give a round a window in the past, then press **Open applications** — it should ask first, and
   then let you.
4. **Rules** and **What we ask for** — the Save sits in a grey bar at the bottom **on the right**,
   and says nothing at all until there is something to say. Hovering a greyed Save still explains
   why.
5. **ms and ta are first drafts** for everything new.

**Not click-tested in a browser** — admin Google sign-in still fails on localhost (TD-182), and
these tabs have no sandbox surface. Structure is covered by rendered tests; the visual sits with
the post-check.

---

## Still open, unchanged by this sprint

- **The gift switcher (the owner's item 3)** — next, on its own. The Applications heading reads
  `{programmeName}`, a BRANDING auto-token, so it names the tenant's flagship whichever gift is
  selected. **Fix the heading first**, then filter the lists.
- Archiving a gift blocks creating a payment run for it (named to the owner, not fixed).
- TD-229, TD-230, TD-231, TD-225, TD-221.
- **The Sabah owner gate stands** — record nothing until it is inked AND the money has moved.
