# Retrospective — the gift setup flow

**Dates:** 2026-09-06 (build) → 2026-09-07 (two live-review rounds, closed same day).
**Branch:** `feat/gift-setup-flow` → `main` at **`ac46f7a6`**. **Three deploys**, each SUCCESS on
both services; final revisions **halatuju-api-00982-2cx** / **halatuju-web-00833-qq2**.

**Migration `scholarship/0150`** — additive, two nullable date columns — **applied migrate-first**
to production and verified before the first push. Ledger reconciled at close: **scholarship
150/150, courses 74/74, no gaps**.

---

## What was asked for, and what it turned out to be

The owner's request was four things:

> *"The setting menu item is missing an icon… Once a programme is created, under Organisation →
> Overview, we need the following to be set as well: Intake Year (with start date and end date) →
> Rules → What we ask for (Questions first, followed by Documents)… Pls investigate if this flow is
> there. We do not want a disconnected flow."*

The investigation found the flow was not there, and that the missing icon was **two** rows, not one.

| what was asked | what was found |
|---|---|
| Settings has no icon | **`orgSettings` AND `faq`** both fell back to a dot, and `navigation.test.ts` mentioned icons **zero times** — so the next new row would do the same |
| Intake year first | Tabs were `Rules · What we ask for · Intake year`, and Create landed on **Rules** |
| Intake year has start + end date | **The columns did not exist.** A migration, not a form field |
| Questions before Documents | Documents rendered first |
| "not a disconnected flow" | Create closed the dialog and **stopped**; the Rules empty state named the Intake year tab **in prose with no button**; there was no `?tab=` deep link for anything to point at |

**Why Rules-first was broken and not merely mis-ordered:** the rules are **columns on the intake
year**. A gift created a minute ago has no year, so Rules had nothing to write to — the first
screen a new gift showed was the one screen that could not work.

---

## What shipped

**A. The icons and their guard.** Two glyphs, plus `icons.test.ts` asserting every id in the
navigation registry has one, **deriving both sides at runtime**. The dot fallback stays — a missing
glyph must not throw inside the shell that renders every admin page — so the loudness lives in the
test.

**B. The order.** `TABS = ['year', 'rules', 'config']`; Questions before Documents.

**C. The window.** `opens_on` / `closes_on`, nullable, no backfill.

**D. The trail.** `?tab=` deep link; Create lands on Intake year; the Rules empty state carries a
button; the year tab points on to Rules **once a year exists**.

**E. One open round per GIFT, and the apply page asks first.** (Owner ruling mid-sprint.)

**F. Deleting a gift** (live-review round two), with the refusal served to the button.

---

## The owner's four rulings, and the one that changed the sprint

1. **"Move the token"** — n/a, that was F7e. Here: **"dates describe."** The dates state when the
   round runs; a person still presses Open.
2. **"One round is open for a gift programme. But if the org has two programmes, there could be two
   open applications."** The guard filtered on `owning_organisation`.
3. **"Type 'delete test2' to confirm"** rather than the bare code.
4. **"I feel it should be prevented at the button stage, and not wait until typed to check."**

**⚠ Ruling 2 corrected a premise of mine, and the correction voided one of my own arguments.** I had
argued for "dates describe" partly on a 3am clash between two gifts opening on the same date. With a
per-gift rule **that clash cannot happen**. The argument is not in the decision record; the one that
survives is that **a clock can fire before setup is finished** — type a start date, get interrupted,
and the round opens with no rules set and no questions configured. A press cannot do that.

---

## What went wrong

### 1. The create flow shipped, and left the owner on a dead screen

**What happened.** They created a gift, were taken to Configuration, and it asked **which** gift —
then every click on the answer did nothing, however many times they pressed.

**Why.** `AppShell` fetches the scopes **once per console session**. A gift created *during* that
session was not in that list, and `programmeScope` then did exactly its job: refused to resolve a
code it did not recognise. `chosen` stayed `''`, `mustChoose` stayed true, forever.

**⚠ THE GUARD WAS NOT THE BUG, AND FIXING IT WOULD HAVE RESTORED A WORSE ONE.** Accepting an unknown
code is the 2026-09-03 defect — it showed the owner a *different programme's settings* — and falling
back to "the only gift" is the same defect wearing a hat. The **list** was stale.

**What I missed.** I wrote `select(wanted)` then `router.push(...)` and reasoned about the
navigation, not about **where the list the selection is validated against comes from**. Two data
sources back one screen (`getAdminProgrammes` fresh per tab, `getAdminScopes` once per shell), and I
only thought about one.

**System change.** `ProgrammeScopeProvider` gained `reload`; the shell's fetch became a re-runnable
`loadScopes`; `create` **awaits** the reload **before** selecting. Recorded in `docs/lessons.md`:
when a write makes a new thing selectable, ask which cached list has to learn about it, and refresh
that list before pointing anyone at it.

### 2. A destructive control the owner was afraid to test

**What happened.** They deleted `test2` and wrote: *"I didn't want to test the brightpath… as it is
risky."*

**Why it matters more than it reads.** The refusal worked — the flagship could never have been
deleted. But **a dangerous button you cannot tell is safe to press is one people avoid**, so they
also cannot tidy up. The guard was correct and the affordance was frightening.

**The trap in the obvious fix.** Disabling the button from the card's own numbers would have been
**wrong in the dangerous direction**: the row carries `intake_years` and `applications` and has
never carried benefactors, money or payment runs, so a gift held by a **donation** would have shown
a green button and refused *after* the phrase was typed — rarer than the bug it replaced, and more
surprising.

**System change.** The server serves `delete_blocked_by`, and **one function** —
`programme_delete_blocker` — fills the row and decides the refusal. Bite-checked: making the row
stop asking fails both new tests.

### 3. `next build` caught a broken page that 1,735 passing tests did not

**What happened.** A leftover `</div>` from my own edit. **jest: 1735 passed. `next lint`: one parse
error. `next build`: failed.**

**Why.** jest renders the components it imports; it never type-checks or compiles the whole tree,
and the file it would have caught this in was not among the ones it mounts.

**⚠ THIS IS THE FOURTH TIME THIS PROJECT HAS RECORDED "`next build` enforces a contract the other
gates do not" — AND THE FIRST WHERE EVERY OTHER GATE WAS GREEN.** Previously it was a Next-specific
page-shape rule; here it was ordinary broken JSX, and the suite sailed past it.

**System change.** None needed — the gate already exists and already caught it. What is recorded is
the *sharper* form of the lesson: green tests are not evidence the tree compiles.

### 4. The new-field trap, three times in one arc

**What happened.** Adding a required field to a TypeScript type broke hand-built fixtures three
separate times: `AdminIntakeYear` gaining the two dates, then `AdminProgramme` gaining the two
delete fields (twice, two files).

**Why.** Every one was a fixture constructing the type by hand — exactly the A3 lesson
(*"when a new field's default changes what an EXISTING row means, every direct constructor in the
suite is in the blast radius"*), which is already in `docs/lessons.md` and which I did not consult
before adding the field.

**System change.** Each fixture now carries the **production shape** (a gift held by its 41
applications; a round with no stated window) rather than a convenient blank, so it says something
true rather than merely compiling. Recorded as a checklist item: after adding a required field to a
shared type, `tsc` **before** running the suite — the suite will not tell you.

### 5. Two bite anchors missed, both on line endings

`views_admin.py` is CRLF and my appended test block was LF, so a byte-exact anchor failed twice.
Both times the fix was to **read the bytes first**, which is already the standing rule. Cheap
because it fails loudly; noted only because it is now the third arc in which it has happened.

---

## What went well

- **Investigating before proposing changed the answer twice.** The "missing icon" was two rows and
  a missing guard; the "delete rules" turned out to be **already written in the model** — every
  relation that means a gift has become something is `on_delete=PROTECT` — so nothing had to be
  invented, only surfaced.
- **The owner's correction was taken as a correction**, and the argument it invalidated was removed
  from the record rather than quietly kept.
- **Every guard this sprint added was bite-checked** (six injections), each verified as landed
  first.
- **The org-fence static guard fired at me and was right** — a pragma sat further than 200
  characters from its query. Moved the pragma, not the guard.

---

## Design decisions

Five, in `docs/decisions.md`: the dates describe; one open round per gift; ask before the form; the
delete rule is the model's; and the button's answer is served, not derived.

---

## Numbers

| gate | at close |
|---|---|
| pytest (`apps/`, FULL) | **5914** |
| jest | **1741** |
| `tsc --noEmit` | **24** (TD-221 baseline) |
| `next lint` | **0 Errors** |
| `check-i18n.js` | **4804 × 3** |
| `next build` | clean |
| migrations | scholarship **150/150**, courses **74/74**, no gaps |

Figures are measured **on the merged tree** — two other agents shipped into `main` during this
sprint (Layer 1 F7f, the grades-stream fix, Org Config Sprint A, the income-panel fix), and the
totals include theirs.

**Three deploys**, which is over the two-per-feature guideline. The second and third were the
owner's live-review rounds finding real defects, not re-attempts at the same change — said here
rather than averaged away.

---

## Owner post-check, still outstanding

1. **BrightPath Bursary's Delete should be grey**, with *"Students have applied to this gift…"*
   underneath. Safe to look at — that is the point of the change.
2. **Delete a spare gift** with the phrase `delete <code>`.
3. **A past start date must leave a round CLOSED.** The one thing this sprint could have got wrong.
4. **ms and ta are first drafts** across everything new here.
